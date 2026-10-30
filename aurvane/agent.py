"""The agent loop, and one plug for any model.

    model proposes an action  ->  guard checks it  ->  world runs it (if allowed)
                 ^                                            |
                 +------------ result goes back --------------+

Models:
  * WorstCaseAgent - offline, no API key. Does the task, and also obeys every
    injected instruction it reads. It is the most gullible agent possible, so it
    tests the guard, not the model.
  * LLMAgent       - any real model (Claude, Grok, local Qwen). It lives in
    `models.py`, with the spending cap.

Held actions (the guard said ASK) wait in `Checkpoint.pending` until a human calls
`approve(id)` or `deny(id)`. Nothing held ever runs on its own.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from .guard import ALLOW, BLOCK, Guard
from .identity import Principal, issue_mandate, issue_passport
from .recorder import FlightRecorder
from .world import TOOLS, UNTRUSTED_SOURCES, World

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


# --- The loop -------------------------------------------------------------------

@dataclass
class RunResult:
    executed: list[Step] = field(default_factory=list)
    blocked: list[Step] = field(default_factory=list)
    held: list[Step] = field(default_factory=list)
    bounded: list[Step] = field(default_factory=list)
    recorder: FlightRecorder | None = None
    error: str = ""   # set if the model failed mid-task; the steps before it still count


class Checkpoint:
    """Aurvane in one object: every tool call passes through `attempt`.

    The agent loop below uses it, and so does the MCP server, so any MCP client
    gets the same protection. A held action waits in `pending` for `approve` or
    `deny`. A sub-agent's checkpoint is built by `delegation.delegate`, which
    passes in a `grant` (passport, mandate, key, chain) instead of a fresh mandate.
    """

    def __init__(self, task: dict, world: World, guarded: bool = True, grant=None, rec=None):
        if grant is None:
            self.human = human = Principal(task.get("human", "Sherif"))
            self.key = Principal(task["agent"])  # the agent's own key, so it can delegate
            self.passport = issue_passport(human, task["agent"], task["role"], agent_key=self.key.public_key)
            self.mandate = issue_mandate(human, self.passport, task["purpose"], task["tools"], **task.get("limits", {}))
            self.chain = None
        else:
            self.passport, self.mandate, self.key, self.chain = grant
            self.human = None
        self.task = task
        self.guard = Guard(self.passport, self.mandate, task["request"], chain=self.chain)
        self.world, self.guarded = world, guarded
        self.rec = rec or FlightRecorder(task["id"])
        self.result = RunResult(recorder=self.rec)
        self.pending: dict[str, Step] = {}
        self._ids = itertools.count(1)
        if grant is None:
            self.rec.log(self.passport.name, "note", f"Mandate issued: {self.mandate.describe()}",
                         mandate=self.mandate.payload(), passport=self.passport.payload())

    def attempt(self, step: Step) -> str:
        spec = TOOLS.get(step.tool)
        if spec is None:
            return "Unknown tool."
        name, res = self.passport.name, self.result
        d = self.guard.check(spec, step.args) if self.guarded else None
        if d is not None and d.outcome == BLOCK:
            res.blocked.append(step)
            self.rec.log(name, "blocked", f"Blocked: {_describe(step)}. {d.reason}.",
                         tool=step.tool, args=step.args, rule=d.rule)
            return f"Denied by Aurvane: {d.reason}"
        if d is not None and d.outcome != ALLOW:
            ask_id = f"ask_{next(self._ids)}"
            self.pending[ask_id] = step
            res.held.append(step)
            self.rec.log(name, "ask", f"Held for you: {_describe(step)}. {d.reason}.",
                         tool=step.tool, args=step.args, rule=d.rule, ask_id=ask_id)
            return f"Held by Aurvane for the human's approval ({ask_id}): {d.reason}"
        return self._execute(step, spec, d)

    def approve(self, ask_id: str) -> str:
        """The human taps Allow. The held action runs, if rules 1-3 still pass."""
        step = self.pending.pop(ask_id)
        spec = TOOLS[step.tool]
        for arg in (spec.payee_arg, spec.recipient_arg, spec.target_arg):
            if arg:  # the human chose this value now, so it counts as trusted from here on
                self.guard.trust(step.args.get(arg))
        d = self.guard.check(spec, step.args)
        if d.outcome == BLOCK:  # e.g. the mandate expired while it waited
            self.rec.log(self.passport.name, "blocked", f"Blocked after approval: {_describe(step)}. {d.reason}.",
                         tool=step.tool, args=step.args, rule=d.rule, ask_id=ask_id)
            return f"Denied by Aurvane: {d.reason}"
        self.result.held.remove(step)
        self.rec.log(self.passport.name, "approved", f"You allowed: {_describe(step)}.",
                     tool=step.tool, args=step.args, ask_id=ask_id)
        return self._execute(step, spec, d)

    def deny(self, ask_id: str) -> str:
        """The human taps Deny. The held action never runs."""
        step = self.pending.pop(ask_id)
        self.rec.log(self.passport.name, "denied", f"You denied: {_describe(step)}.",
                     tool=step.tool, args=step.args, ask_id=ask_id)
        return "Denied by the human."

    def _execute(self, step: Step, spec, d) -> str:
        res = self.result
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
        self.rec.log(self.passport.name, "action" if spec.privileged else "read", _describe(step) + note,
                     tool=step.tool, args=step.args, untrusted=step.tool in UNTRUSTED_SOURCES)
        return output


def run(task: dict, model, world: World, guarded: bool = True, max_steps: int = 25) -> RunResult:
    """Run one task: the model proposes, the checkpoint decides, the world answers."""
    cp = Checkpoint(task, world, guarded)
    last = (None, None, None)
    for _ in range(max_steps):
        try:
            step = model.next_action(*last)
        except Exception as e:  # a provider error or the spending cap: keep what already happened
            cp.result.error = f"{type(e).__name__}: {e}"
            break
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
