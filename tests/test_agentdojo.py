"""The AgentDojo numbers: the README says what the result file says, and the result file reruns.

The first test needs nothing. The second needs `pip install -e ".[dojo]"` and is skipped without it
(CI does not install the benchmark); it replays one suite, about ten seconds.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = json.loads((ROOT / "bench" / "results" / "agentdojo_summary.json").read_text())


def test_readme_quotes_the_result_file():
    readme = (ROOT / "README.md").read_text()
    section = readme[readme.index("## On the public benchmark: AgentDojo"):readme.index("## Red team")]
    for cond in ("none", "A", "B"):
        t = SUMMARY["conditions"][cond]["total"]
        for count, pct in (("attack_success", "attack_success_pct"), ("clean_ok", "clean_utility_pct"),
                           ("clean_need_approval", "clean_need_approval_pct"), ("utility_under_attack", "utility_under_attack_pct")):
            assert f"{t[count]} ({t[pct]}%)" in section, (cond, count)
    a = SUMMARY["conditions"]["A"]
    assert f"the {a['total']['pairs']} pairs" in section and f"({a['total']['pairs_not_replayable']} more" in section
    for name, s in a["suites"].items():
        assert f"**{s['attack_success']}/{s['pairs']}**" in section, name
    for key, v in a["by_injection_task"].items():
        if v["landed"]:
            assert f"{v['landed']} of {v['pairs']}" in section, key
    assert sum(v["landed"] for v in a["by_injection_task"].values()) == a["total"]["attack_success"]


def test_protocol_was_committed_before_the_results():
    protocol = (ROOT / "bench" / "agentdojo" / "PROTOCOL.md").read_text()
    assert "before the guard was run on any AgentDojo task" in protocol
    assert "Nothing in \"How the guard is attached\" was changed." in protocol


def test_one_suite_reruns_to_the_committed_numbers():
    pytest.importorskip("agentdojo")
    spec = importlib.util.spec_from_file_location("agentdojo_run", ROOT / "bench" / "agentdojo" / "run.py")
    run = importlib.util.module_from_spec(spec)
    sys.modules["agentdojo_run"] = run
    spec.loader.exec_module(run)
    fresh, _ = run.run(["none", "A", "B"], ["banking"])
    for cond in ("none", "A", "B"):
        assert fresh["conditions"][cond]["suites"]["banking"] == SUMMARY["conditions"][cond]["suites"]["banking"], cond
