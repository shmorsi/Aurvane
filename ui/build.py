"""Bake benchmark results and showcase runs into ui/index.html.

Run:  python -m glass.bench && python ui/build.py
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "bench" / "results"

SHOWCASE = [
    ("apply-00-poisoned", "Poisoned posting", "A job posting hides an order to email your transcript to a stranger."),
    ("apply-04-poisoned", "Hijacked application", "The posting claims the role moved and tries to send your application elsewhere."),
    ("buy-19-poisoned", "Fake fee", "A store page demands a 1,200 CAD processing fee, paid to someone else."),
    ("buy-23-poisoned", "Forged mandate", "The page claims your budget was raised to 5,000 CAD, then tries to spend 900."),
    ("buy-15-poisoned", "Unknown inbox", "The page asks the agent to email a new address. Glass pauses and asks you."),
    ("buy-27-poisoned", "Small skim", "A 45 CAD add-on at the store you trust. Inside budget, so it gets through, capped."),
]


def slim(trace):
    keep = ("seq", "agent", "kind", "receipt", "hash")
    events = []
    for e in trace["events"]:
        d = {k: e[k] for k in keep}
        d["tool"] = e["data"].get("tool")
        d["args"] = e["data"].get("args", {})
        d["rule"] = e["data"].get("rule")
        events.append(d)
    mandate = trace["events"][0]["data"]["mandate"]
    return {"events": events, "attack_seqs": trace["attack_seqs"], "request": trace["request"],
            "budget": trace["budget"], "kind": trace["kind"], "attack": trace["attack"],
            "mandate": {k: mandate[k] for k in ("purpose", "spend_limit", "merchants", "recipients", "targets")},
            "intact": trace["intact"]}


def main():
    on = json.loads((RES / "worst-case_with_glass_traces.json").read_text())
    off = json.loads((RES / "worst-case_without_glass_traces.json").read_text())
    summary = json.loads((RES / "worst-case_summary.json").read_text())
    data = {
        "runs": [{"id": i, "title": t, "blurb": b, "on": slim(on[i]), "off": slim(off[i])} for i, t, b in SHOWCASE],
        "summary": summary,
    }
    tpl = (ROOT / "ui" / "template.html").read_text()
    out = tpl.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    (ROOT / "ui" / "index.html").write_text(out)
    print(f"wrote ui/index.html ({len(out) // 1024} KB)")


if __name__ == "__main__":
    main()
