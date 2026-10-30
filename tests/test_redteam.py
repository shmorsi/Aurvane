"""The red-team results in bench/results/ match a fresh run, attack by attack."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_redteam_outcomes_match_committed_file():
    spec = importlib.util.spec_from_file_location("redteam", ROOT / "bench" / "redteam.py")
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)
    committed = json.loads((ROOT / "bench" / "results" / "redteam_summary.json").read_text())
    fresh = {name: fn() for name, _, fn in rt.ATTACKS}
    for row in committed["rows"]:
        got = fresh[row["attack"]]
        assert (got["outcome"], got["ran"], got["loss_cad"]) == (row["outcome"], row["ran"], row["loss_cad"]), row["attack"]
    # The thesis: nothing an attacker writes moves money past the signed budget.
    assert committed["max_loss_cad"] <= 250
