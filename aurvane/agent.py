"""The agent loop, and one plug for any model.

    model proposes an action  ->  guard checks it  ->  world runs it (if allowed)
                 ^                                            |
                 +------------ result goes back --------------+

Models:
  * WorstCaseAgent - offline, no API key. Does the task, and also obeys every
    injected instruction it reads. It is the most gullible agent possible, so it
    tests the guard, not the model.
  * LLMAgent       - any real model: Claude (Anthropic API), Grok (xAI), local
    Qwen via Ollama, or anything OpenAI-compatible.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field

from .guard import ALLOW, BLOCK, Guard
from .identity import Principal, issue_mandate, issue_passport
from .recorder import FlightRecorder
from .world import TOOLS, UNTRUSTED_SOURCES, World

SCHEMAS = {
    "read_posting": {"posting_id": "string"},
    "read_store": {"merchant": "string"},
    "read_file": {"path": "string"},
    "write_draft": {"kind": "string", "text": "string"},
    "submit_application": {"posting_id": "string", "documents": "string"},
    "send_email": {"to": "string", "subject": "string", "body": "string"},
    "pay": {"merchant": "string", "amount": "number", "memo": "string"},
}


@dataclass
class Step:
    tool: str
    args: dict


# --- Models ---------------------------------------------------------------------

class WorstCaseAgent:
    """Follows a plan, and obeys any injection it reads, right away."""

    def __init__(self, plan: list[Step], injections: dict[str, list[Step]]):
        self.queue = list(plan)
        self.injections = injections  # source id -> actions the attacker wants

    def next_action(self, last_tool: str | None, last_args: dict | None, last_output: str | None):
        if last_tool in UNTRUSTED_SOURCES and last_args:
            source = last_args.get("posting_id") or last_args.get("merchant")
            self.queue = list(self.injections.pop(source, [])) + self.queue
        return self.queue.pop(0) if self.queue else None


class LLMAgent:
    """A real model behind one interface. provider: anthropic | openai-compatible."""

    def __init__(self, provider: str, model: str, task: str, base_url: str | None = None, api_key: str | None = None):
        self.provider, self.model = provider, model
        self.base_url = base_url or {
            "anthropic": "https://api.anthropic.com/v1",
            "xai": "https://api.x.ai/v1",
            "ollama": "http://localhost:11434/v1",
        }.get(provider, "https://api.openai.com/v1")
        self.api_key = api_key or os.environ.get(
            {"anthropic": "ANTHROPIC_API_KEY", "xai": "XAI_API_KEY"}.get(provider, "OPENAI_API_KEY"), "ollama")
        self.messages = [{"role": "user", "content": task + "\nUse the tools. Reply DONE when finished."}]
        self._pending_id = None

    def next_action(self, last_tool, last_args, last_output):
        if self._pending_id is not None:
            self._append_result(last_output or "")
        msg = self._call()
        if msg is None:
            return None
        tool, args, call_id = msg
        self._pending_id = call_id
        return Step(tool, args)

    def _tools(self):
        out = []
        for name, props in SCHEMAS.items():
            schema = {"type": "object", "properties": {k: {"type": t} for k, t in props.items()},
                      "required": list(props)}
            if self.provider == "anthropic":
                out.append({"name": name, "description": name.replace("_", " "), "input_schema": schema})
            else:
                out.append({"type": "function", "function": {"name": name, "parameters": schema}})
        return out

    def _post(self, path, body, headers):
        req = urllib.request.Request(self.base_url + path, json.dumps(body).encode(),
                                     {"content-type": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)

    def _call(self):
        if self.provider == "anthropic":
            r = self._post("/messages", {"model": self.model, "max_tokens": 1024,
                                         "messages": self.messages, "tools": self._tools(),
                                         "tool_choice": {"type": "auto", "disable_parallel_tool_use": True}},
                           {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
            self.messages.append({"role": "assistant", "content": r["content"]})
            for block in r["content"]:
                if block["type"] == "tool_use":
                    return block["name"], block["input"], block["id"]
            return None
        r = self._post("/chat/completions", {"model": self.model, "messages": self.messages,
                                             "tools": self._tools(), "parallel_tool_calls": False},
                       {"authorization": f"Bearer {self.api_key}"})
        msg = r["choices"][0]["message"]
        self.messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return None
        c = calls[0]
        return c["function"]["name"], json.loads(c["function"]["arguments"] or "{}"), c["id"]

    def _append_result(self, output):
        if self.provider == "anthropic":
            self.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": self._pending_id, "content": output}]})
        else:
            self.messages.append({"role": "tool", "tool_call_id": self._pending_id, "content": output})
        self._pending_id = None


# --- The loop -------------------------------------------------------------------

@dataclass
class RunResult:
    executed: list[Step] = field(default_factory=list)
    blocked: list[Step] = field(default_factory=list)
    held: list[Step] = field(default_factory=list)
    bounded: list[Step] = field(default_factory=list)
    recorder: FlightRecorder | None = None


class Checkpoint:
    """Aurvane in one object: every tool call passes through `attempt`.

    The agent loop below uses it, and so does the MCP server, so any MCP client
    gets the same protection.
    """

    def __init__(self, task: dict, world: World, guarded: bool = True):
        human = Principal(task.get("human", "Sherif"))
        self.passport = issue_passport(human, task["agent"], task["role"])
        self.mandate = issue_mandate(human, self.passport, task["purpose"], task["tools"], **task.get("limits", {}))
        self.guard = Guard(self.passport, self.mandate, task["request"])
        self.world, self.guarded = world, guarded
        self.rec = FlightRecorder(task["id"])
        self.result = RunResult(recorder=self.rec)
        self.rec.log(self.passport.name, "note", f"Mandate issued: {self.mandate.describe()}",
                     mandate=self.mandate.payload(), passport=self.passport.payload())

    def attempt(self, step: Step) -> str:
        spec = TOOLS.get(step.tool)
        if spec is None:
            return "Unknown tool."
        name, res = self.passport.name, self.result
        d = self.guard.check(spec, step.args) if self.guarded else None
        if d is not None and d.outcome != ALLOW:
            blocked = d.outcome == BLOCK
            (res.blocked if blocked else res.held).append(step)
            self.rec.log(name, "blocked" if blocked else "ask",
                         f"{'Blocked' if blocked else 'Held for you'}: {_describe(step)}. {d.reason}.",
                         tool=step.tool, args=step.args, rule=d.rule)
            return f"Denied by Aurvane: {d.reason}"
        output = self.world.call(step.tool, step.args)
        if self.guarded:
            self.guard.commit(spec, step.args)
            if step.tool in UNTRUSTED_SOURCES:
                self.guard.saw_untrusted(output)
        res.executed.append(step)
        bounded = d is not None and d.bounded
        if bounded:
            res.bounded.append(step)
        note = " (amount from untrusted text; capped by budget)" if bounded else ""
        self.rec.log(name, "action" if spec.privileged else "read", _describe(step) + note,
                     tool=step.tool, args=step.args, untrusted=step.tool in UNTRUSTED_SOURCES)
        return output


def run(task: dict, model, world: World, guarded: bool = True, max_steps: int = 25) -> RunResult:
    """Run one task: the model proposes, the checkpoint decides, the world answers."""
    cp = Checkpoint(task, world, guarded)
    last = (None, None, None)
    for _ in range(max_steps):
        step = model.next_action(*last)
        if step is None:
            break
        last = (step.tool, step.args, cp.attempt(step))
    return cp.result


def _describe(s: Step) -> str:
    a = s.args
    return {
        "read_posting": lambda: f"Read posting {a.get('posting_id')}",
        "read_store": lambda: f"Read store page {a.get('merchant')}",
        "read_file": lambda: f"Opened {a.get('path')}",
        "write_draft": lambda: f"Drafted {a.get('kind')}",
        "submit_application": lambda: f"Submit application to {a.get('posting_id')}",
        "send_email": lambda: f"Email {a.get('to')}",
        "pay": lambda: f"Pay {a.get('amount')} to {a.get('merchant')}",
    }.get(s.tool, lambda: s.tool)()
