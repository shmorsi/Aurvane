"""Real models behind one plug, with a hard spending cap.

The benchmark asks a model "what next?" through one method, `next_action`. This
file answers it with a real model: Muse Spark (Meta Model API), Claude (Anthropic
API), Grok (xAI), or an open-weights model through a local Ollama server. Every
provider but Anthropic speaks the OpenAI-compatible chat completions API.

Vision: when a tool returns a `Screenshot` (a page the agent can only see), the
model gets the picture itself. In the OpenAI-compatible format a tool message
carries text only, so the caption goes in the tool message and the picture follows
in a user message; Anthropic takes the picture inside the tool result.

Real models cost real money, so every call goes through a `SpendCap`. Before a
call, it prices the worst case (the whole prompt plus the longest possible reply)
and refuses if that could push the running total over the cap. After the call, it
adds the real cost from the provider's usage numbers. The running total lives in
`bench/results/spend.json`, so the cap holds across separate runs too.
"""
from __future__ import annotations

import base64
import datetime
import http.client
import json
import mimetypes
import os
import urllib.error
import urllib.request

from .world import Screenshot

# USD per million tokens: (input, output). Cache reads cost 0.1x input, cache writes 1.25x.
# A model missing here needs `--price in,out`, so the cap is never enforced against a guess.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
# Meta Model API: OpenAI-compatible. Override with --base-url if your console shows another.
BASE_URLS = {"meta": "https://api.meta.ai/v1", "anthropic": "https://api.anthropic.com/v1",
             "xai": "https://api.x.ai/v1", "ollama": "http://localhost:11434/v1"}
KEYS = {"meta": "META_MODEL_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "xai": "XAI_API_KEY"}
MAX_TOKENS = 4096


def image_data_url(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()

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


def vision_json(provider: str, model: str, prompt: str, image_path: str, cap: SpendCap,
                base_url: str | None = None, api_key: str | None = None) -> tuple[dict, str]:
    """One question about one picture, answered as JSON. Returns (parsed, raw text).

    Used by `aurvane.evidence` to ask a vision model where on a page an instruction
    was drawn. Parsing is forgiving (a fenced block or prose around the object is fine);
    an answer with no JSON object comes back as {} with the raw text kept for the record.
    """
    agent = LLMAgent(provider, model, "", cap, base_url=base_url, api_key=api_key)
    url = image_data_url(image_path)
    if provider == "anthropic":
        media, data = url[5:].split(";base64,")
        content = [{"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                   {"type": "text", "text": prompt}]
        r = agent._post("/messages", {"model": model, "max_tokens": 1024,
                                      "messages": [{"role": "user", "content": content}]},
                        {"x-api-key": agent.api_key, "anthropic-version": "2023-06-01"})
        u = r.get("usage", {})
        cap.add(u.get("input_tokens", 0), u.get("output_tokens", 0))
        raw = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
    else:
        content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]
        r = agent._post("/chat/completions", {"model": model, "messages": [{"role": "user", "content": content}]},
                        {"authorization": f"Bearer {agent.api_key}"})
        u = r.get("usage", {})
        cap.add(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        raw = r["choices"][0]["message"].get("content") or ""
    return parse_json_object(raw), raw


def parse_json_object(text: str) -> dict:
    """The first {...} object in a reply that parses, or {}."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    return obj if isinstance(obj, dict) else {}
                except json.JSONDecodeError:
                    break
        start = text.find("{", start + 1)
    return {}


def ping(provider: str, model: str, cap: SpendCap, base_url: str | None = None) -> str:
    """One tiny call, to check the key, the base URL and the model ID before a run spends anything."""
    agent = LLMAgent(provider, model, "", cap, base_url=base_url)
    if provider == "anthropic":
        r = agent._post("/messages", {"model": model, "max_tokens": 16, "messages": [{"role": "user", "content": "Reply OK."}]},
                        {"x-api-key": agent.api_key, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in r.get("content", []))
    r = agent._post("/chat/completions", {"model": model, "messages": [{"role": "user", "content": "Reply OK."}]},
                    {"authorization": f"Bearer {agent.api_key}"})
    u = r.get("usage", {})
    cap.add(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
    return r["choices"][0]["message"].get("content") or ""


class LLMAgent:
    """A real model behind one interface. provider: meta | anthropic | xai | ollama | any OpenAI-compatible."""

    def __init__(self, provider: str, model: str, task: str, cap: SpendCap,
                 base_url: str | None = None, api_key: str | None = None):
        self.provider, self.model, self.cap = provider, model, cap
        self.base_url = base_url or BASE_URLS.get(provider, "https://api.openai.com/v1")
        self.api_key = api_key or os.environ.get(KEYS.get(provider, "OPENAI_API_KEY"), "ollama")
        self.messages = [{"role": "user", "content": task + "\nUse the tools. Reply DONE when finished."}]
        self._pending_id = None
        self._parallel_flag = True
        self.stop_reason = ""
        self.notes: list[str] = []

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
        except (http.client.HTTPException, ConnectionError, TimeoutError, json.JSONDecodeError) as e:
            # a dropped connection, a timeout or a non-JSON body: the task fails and is reported, never retried
            raise ModelError(f"{type(e).__name__}: {e}") from e

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
        body = {"model": self.model, "messages": self.messages, "tools": self._tools()}
        if self._parallel_flag:
            body["parallel_tool_calls"] = False
        try:
            r = self._post("/chat/completions", body, {"authorization": f"Bearer {self.api_key}"})
        except ModelError as e:
            # Some OpenAI-compatible servers reject the flag. Drop it once and say so in the
            # trace; the loop still runs one tool call per turn (it uses only the first call).
            if not (self._parallel_flag and e.args and str(e.args[0]).startswith("400")
                    and "parallel_tool_calls" in str(e.args[0])):
                raise
            self._parallel_flag = False
            self.notes.append("provider rejected parallel_tool_calls; sent without it")
            body.pop("parallel_tool_calls")
            r = self._post("/chat/completions", body, {"authorization": f"Bearer {self.api_key}"})
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
        picture = getattr(output, "path", None) if isinstance(output, Screenshot) else None
        text = str(output)
        if self.provider == "anthropic":
            content = text
            if picture:
                media, data = image_data_url(picture)[5:].split(";base64,")
                content = [{"type": "text", "text": text},
                           {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}]
            self.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": self._pending_id, "content": content}]})
        else:
            self.messages.append({"role": "tool", "tool_call_id": self._pending_id, "content": text})
            if picture:
                self.messages.append({"role": "user", "content": [
                    {"type": "text", "text": "The screenshot returned by that tool call:"},
                    {"type": "image_url", "image_url": {"url": image_data_url(picture)}}]})
        self._pending_id = None


if __name__ == "__main__":  # python -m aurvane.models <provider> <model> [base_url]
    import sys
    args = sys.argv[1:]
    if len(args) < 2:
        raise SystemExit("usage: python -m aurvane.models <provider> <model> [base_url]")
    if args[0] in KEYS and not os.environ.get(KEYS[args[0]]):
        raise SystemExit(f"{KEYS[args[0]]} is not set")
    print(repr(ping(args[0], args[1], SpendCap(0.05, price=(10.0, 10.0)), args[2] if len(args) > 2 else None)[:200]))
