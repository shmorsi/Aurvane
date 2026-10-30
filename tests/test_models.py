"""The real-model harness, tested offline against a scripted fake provider.

No network and no API key: `_post` is replaced by a function that answers in the
Anthropic wire format, so the loop, the cost meter, the cap and the analysis all
run exactly as they would against the real API.
"""
import json

import pytest

from aurvane import bench
from aurvane.models import CapReached, LLMAgent, SpendCap
from aurvane.stats import analyse, mcnemar_exact, summarize


def fake_claude(task):
    """Plays the worst-case agent, but through the Anthropic message format."""
    plan = list(task["plan"])
    injections = {k: list(v) for k, v in task["injections"].items()}

    def post(self, path, body, headers):
        assert path == "/messages" and "temperature" not in body
        assert headers["anthropic-version"] and body["tool_choice"]["type"] == "auto"
        self.cap.check(len(json.dumps(body)))
        last = body["messages"][-1]["content"]
        step = None
        if isinstance(last, list):  # a tool result came back
            prev = self.messages[-2]["content"][0]["input"]
            source = prev.get("posting_id") or prev.get("merchant")
            plan[:0] = injections.pop(source, [])
        if plan:
            step = plan.pop(0)
        usage = {"input_tokens": 1000, "output_tokens": 100}
        if step is None:
            return {"content": [{"type": "text", "text": "DONE"}], "stop_reason": "end_turn", "usage": usage}
        return {"content": [{"type": "tool_use", "id": f"t{len(self.messages)}", "name": step.tool,
                             "input": step.args}], "stop_reason": "tool_use", "usage": usage}
    return post


def run_fake(monkeypatch, cap):
    def make(task):
        monkeypatch.setattr(LLMAgent, "_post", fake_claude(task))
        return LLMAgent("anthropic", "claude-haiku-5-5", task["request"], cap, api_key="test")
    off, _ = bench.run_all(make, guarded=False)
    on, _ = bench.run_all(make, guarded=True)
    return off, on


def test_fake_provider_reproduces_the_worst_case_numbers(monkeypatch):
    cap = SpendCap(5.0, price=(0.10, 0.50))
    off, on = run_fake(monkeypatch, cap)
    assert summarize(off)["attacks_landed"] == 30
    assert summarize(on)["attacks_landed"] == 7 and summarize(on)["clean_completed"] == 30
    a = analyse(off, on)
    assert a["H1_without_at_least_one_attack_lands"] and a["H2_with_no_blocked_type_lands"] and a["H3_holds"]
    assert 0 < cap.spent < 5.0


def test_cap_stops_the_run_and_says_so(monkeypatch):
    cap = SpendCap(0.002, price=(0.10, 0.50))
    off, _ = run_fake(monkeypatch, cap)
    s = summarize(off)
    assert s["stopped_early"] and not s["complete"]
    assert cap.total <= 0.002


def test_cap_refuses_a_call_that_could_cross_it():
    cap = SpendCap(1.0, price=(4.0, 20.0))
    cap.spent = 0.95
    with pytest.raises(CapReached):
        cap.check(10_000)


def test_ledger_keeps_the_cap_across_runs(tmp_path):
    ledger = str(tmp_path / "spend.json")
    first = SpendCap(5.0, ledger, price=(1.0, 1.0))
    first.add(inp=1_000_000)
    first.save("anthropic", "m")
    second = SpendCap(5.0, ledger, price=(1.0, 1.0))
    assert second.total == 1.0


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 0) == 0.0625
    assert mcnemar_exact(3, 1) == 0.625
