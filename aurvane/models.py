"""Real models behind one plug, with a hard spending cap.

The benchmark asks a model "what next?" through one method, `next_action`. This
file answers it with a real model: Claude (Anthropic API), Grok (xAI), or Qwen
through a local Ollama server, which speaks the OpenAI-compatible API.

Real models cost real money, so every call goes through a `SpendCap`. Before a
call, it prices the worst case (the whole prompt plus the longest possible reply)
and refuses if that could push the running total over the cap. After the call, it
adds the real cost from the provider's usage numbers. The running total lives in
`bench/results/spend.json`, so the cap holds across separate runs too.
"""
from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request

# USD per million tokens: (input, output). Cache reads cost 0.1x input, cache writes 1.25x.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
BASE_URLS = {"anthropic": "https://api.anthropic.com/v1", "xai": "https://api.x.ai/v1",
             "ollama": "http://localhost:11434/v1"}
KEYS = {"anthropic": "ANTHROPIC_API_KEY", "xai": "XAI_API_KEY"}
MAX_TOKENS = 4096

SCHEMAS = {
    "read_posting": {"posting_id": "string"},
    "read_store": {"merchant": "string"},
    "read_file": {"path": "string"},
    "write_draft": {"kind": "string", "text": "string"},
    "submit_application": {"posting_id": "string", "documents": "string"},
    "send_email": {"to": "string", "subject": "string", "body": "string"},
    "pay": {"merchant": "string", "amount": "number", "memo": "string"},
}


class CapReached(RuntimeError):
    """The next call could cross the spending cap, so it was not made."""


class ModelError(RuntimeError):
    """The provider returned an error. The task is recorded as failed, not skipped."""


class SpendCap:
    def __init__(self, cap_usd: float, ledger: str | None = None, price: tuple[float, float] = (0.0, 0.0)):
        self.cap, self.ledger, self.price = cap_usd, ledger, price
        self.before = 0.0  # spent by earlier runs, from the ledger
        if ledger and os.path.exists(ledger):
            with open(ledger) as f:
                self.before = json.load(f).get("total_usd", 0.0)
        self.spent = 0.0   # spent by this run

    @property
    def total(self) -> float:
        return self.before + self.spent

    def check(self, prompt_chars: int) -> None:
        p_in, p_out = self.price
        worst = (prompt_chars / 3 * p_in + MAX_TOKENS * p_out) / 1e6  # ~3 chars per token, generous
        if self.total + worst > self.cap:
            raise CapReached(f"next call could cost {worst:.4f} USD; {self.total:.4f} of {self.cap:.2f} spent")

    def add(self, inp=0, out=0, cache_read=0, cache_write=0) -> float:
        p_in, p_out = self.price
        usd = (inp * p_in + cache_write * p_in * 1.25 + cache_read * p_in * 0.1 + out * p_out) / 1e6
        self.spent += usd
        return usd

    def save(self, provider: str, model: str) -> None:
        if not self.ledger:
            return
        data = {"total_usd": 0.0, "runs": []}
        if os.path.exists(self.ledger):
            with open(self.ledger) as f:
                data = json.load(f)
        data["runs"].append({"provider": provider, "model": model, "usd": round(self.spent, 4),
                             "date": datetime.date.today().isoformat()})
        data["total_usd"] = round(self.before + self.spent, 4)
        with open(self.ledger, "w") as f:
            json.dump(data, f, indent=2)


class LLMAgent:
    """A real model behind one interface. provider: anthropic | xai | ollama | any OpenAI-compatible."""

    def __init__(self, provider: str, model: str, task: str, cap: SpendCap,
                 base_url: str | None = None, api_key: str | None = None):
        self.provider, self.model, self.cap = provider, model, cap
        self.base_url = base_url or BASE_URLS.get(provider, "https://api.openai.com/v1")
        self.api_key = api_key or os.environ.get(KEYS.get(provider, "OPENAI_API_KEY"), "ollama")
        self.messages = [{"role": "user", "content": task + "\nUse the tools. Reply DONE when finished."}]
        self._pending_id = None
        self.stop_reason = ""

    def next_action(self, last_tool, last_args, last_output):
        from .agent import Step
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
        data = json.dumps(body).encode()
        self.cap.check(len(data))
        req = urllib.request.Request(self.base_url + path, data, {"content-type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise ModelError(f"{e.code} {e.read()[:300].decode(errors='replace')}") from e
        except urllib.error.URLError as e:
            raise ModelError(str(e.reason)) from e

    def _call(self):
        if self.provider == "anthropic":
            # No temperature: the protocol fixes it at the provider default.
            r = self._post("/messages", {"model": self.model, "max_tokens": MAX_TOKENS,
                                         "messages": self.messages, "tools": self._tools(),
                                         "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
                                         "cache_control": {"type": "ephemeral"}},
                           {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
            u = r.get("usage", {})
            self.cap.add(u.get("input_tokens", 0), u.get("output_tokens", 0),
                         u.get("cache_read_input_tokens", 0) or 0, u.get("cache_creation_input_tokens", 0) or 0)
            self.stop_reason = r.get("stop_reason", "")
            self.messages.append({"role": "assistant", "content": r["content"]})  # thinking blocks kept unchanged
            for block in r["content"]:
                if block["type"] == "tool_use":
                    return block["name"], block["input"], block["id"]
            return None
        r = self._post("/chat/completions", {"model": self.model, "messages": self.messages,
                                             "tools": self._tools(), "parallel_tool_calls": False},
                       {"authorization": f"Bearer {self.api_key}"})
        u = r.get("usage", {})
        self.cap.add(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        msg = r["choices"][0]["message"]
        self.stop_reason = r["choices"][0].get("finish_reason", "")
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
