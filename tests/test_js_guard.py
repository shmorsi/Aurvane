"""The browser guard (ui/guard.js) and the Python guard decide the same way.

Every one of the 60 benchmark tasks runs through the Python checkpoint. Each call
the checkpoint makes to its guard (check, commit, saw_untrusted) is recorded, plus
a set of probe actions after the run. Node then replays the same calls into the JS
guard, and the test fails if any outcome, rule, reason or "bounded" flag differs.
"""
import dataclasses
import json
import pathlib
import shutil
import subprocess

import pytest

from aurvane.agent import Checkpoint, Step, WorstCaseAgent
from aurvane.bench import ME, make_tasks
from aurvane.world import TOOLS, World

ROOT = pathlib.Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

NODE = r"""
const g = require(process.argv[1]);
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = { checks: 0, mismatches: [], tools: g.TOOLS };
for (const c of cases) {
  const guard = new g.Guard(c.passport, c.mandate, c.task_text, c.verified);
  for (const op of c.ops) {
    if (op.op === "untrusted") guard.sawUntrusted(op.text);
    else if (op.op === "commit") guard.commit(g.TOOLS[op.tool], op.args);
    else {
      const d = guard.check(g.TOOLS[op.tool], op.args);
      const js = [d.outcome, d.rule, d.reason, d.bounded];
      out.checks++;
      if (JSON.stringify(js) !== JSON.stringify(op.py)) out.mismatches.push({ task: c.id, tool: op.tool, args: op.args, py: op.py, js });
    }
  }
}
console.log(JSON.stringify(out));
"""


def probes(task, cp):
    m = cp.mandate
    stranger = "verify@id-desk9.example"
    out = [Step("read_store", {"merchant": "x"}), Step("read_posting", {"posting_id": "P-1"})]
    for merchant in (*m.merchants, "fastpay-fees.example"):
        for amount in (45, 45.0, 199, "199", 250, 251, 1200, 0.5, 1234567):
            out.append(Step("pay", {"merchant": merchant, "amount": amount, "memo": "probe"}))
    for to in (ME, f"  {ME.upper()} ", stranger, "sherif@inbox.example.evil"):
        out.append(Step("send_email", {"to": to, "subject": "s", "body": "b"}))
    for pid in (*m.targets, "P-999", "p-100"):
        out.append(Step("submit_application", {"posting_id": pid, "documents": "resume.md"}))
    return out


def record(task, expired=False):
    cp = Checkpoint(task, World(postings=dict(task["world"].get("postings", {})), stores=dict(task["world"].get("stores", {}))))
    if expired:
        cp.mandate = cp.guard.mandate = dataclasses.replace(cp.mandate, expires_at=0)
    g, ops = cp.guard, []
    check, commit, saw = g.check, g.commit, g.saw_untrusted

    def rec_check(spec, args):
        d = check(spec, args)
        ops.append({"op": "check", "tool": spec.name, "args": args, "py": [d.outcome, d.rule, d.reason, d.bounded]})
        return d

    g.check = rec_check
    g.commit = lambda spec, args: (ops.append({"op": "commit", "tool": spec.name, "args": args}), commit(spec, args))
    g.saw_untrusted = lambda text: (ops.append({"op": "untrusted", "text": text}), saw(text))
    agent = WorstCaseAgent(task["plan"], {k: list(v) for k, v in task["injections"].items()})
    last = (None, None, None)
    while (step := agent.next_action(*last)) is not None:
        last = (step.tool, step.args, cp.attempt(step))
    for step in probes(task, cp):
        g.check(TOOLS[step.tool], step.args)
    return {"id": task["id"], "passport": {"agent_id": cp.passport.agent_id}, "mandate": cp.mandate.payload(),
            "task_text": task["request"], "verified": {"passport": cp.passport.is_valid(), "mandate": cp.mandate.is_valid()},
            "ops": ops}


def test_js_and_python_guards_agree_on_all_60_tasks():
    tasks = make_tasks()
    cases = [record(t) for t in tasks] + [record(tasks[0], expired=True), record(tasks[31], expired=True)]
    r = subprocess.run(["node", "-e", NODE, str(ROOT / "ui" / "guard.js")], input=json.dumps(cases),
                       capture_output=True, text=True, check=True)
    out = json.loads(r.stdout)
    assert out["mismatches"] == [], out["mismatches"][:5]
    assert out["checks"] > 60 * 25  # every task, plus about 20 probes each
    outcomes = {op["py"][0] for c in cases for op in c["ops"] if op["op"] == "check"}
    assert outcomes == {"allow", "block", "ask"}
    py_tools = {k: {f: v for f, v in dataclasses.asdict(s).items() if v} for k, s in TOOLS.items()}
    assert out["tools"] == py_tools
