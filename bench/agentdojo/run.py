"""Aurvane on AgentDojo, by the protocol in bench/agentdojo/PROTOCOL.md.

    pip install -e . agentdojo==0.1.35
    python bench/agentdojo/run.py                    # every condition -> bench/results/agentdojo_*.json
    python bench/agentdojo/run.py --only none        # the harness check alone (protocol, E1)

A worst-case agent with no model: for each of AgentDojo's user-task and injection-task pairs it
replays the user task's ground-truth tool calls, then the attacker's. The guard is the one in
aurvane/guard.py, unchanged; this file only tells it, from a tool's name and argument names, what
kind of action a call is (protocol, "How the guard is attached"). AgentDojo's own utility and
security checks do the scoring. No API key, no randomness in the results.
"""

from __future__ import annotations

import argparse
import json
import warnings
from collections import defaultdict
from pathlib import Path

from agentdojo.agent_pipeline import ground_truth_pipeline as gtp
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.task_suite.load_suites import get_suites

from aurvane.guard import ALLOW, ASK, BLOCK, Guard, ToolSpec
from aurvane.identity import Principal, issue_mandate, issue_passport

VERSION = "v1.2.2"
ROOT = Path(__file__).resolve().parents[2]

# Protocol, rule 1: a read-only tool, by its name.
READ = ("get_", "search_", "read_", "list_", "check_")
# Protocol, rule 3: the control values of a privileged call, by argument name.
PAYEE = {"hotel", "restaurant", "company"}
RECIPIENT = {"recipient", "recipients", "cc", "bcc", "participants", "email", "user_email", "channel", "url", "user"}
TARGET = {"id", "event_id", "email_id", "file_id"}
CONDITIONS = {"none": "Without Aurvane", "A": "With Aurvane (A: payees, recipients, targets)", "B": "With Aurvane (B: payees and recipients only)"}
RANK = {ALLOW: 0, ASK: 1, BLOCK: 2}


def controls(args: dict, params: set[str], targets: bool) -> list[tuple[str, object]]:
    """(role, value) for every control value in a call: a list gives one pair an element."""
    out = []
    for key, value in args.items():
        if key == "recipient":
            role = "payee" if "amount" in params else "recipient"
        elif key in PAYEE:
            role = "payee"
        elif key in RECIPIENT:
            role = "recipient"
        elif key in TARGET and targets:
            role = "target"
        else:
            continue
        for item in value if isinstance(value, (list, tuple)) else [value]:
            if item not in (None, "", [], ()):
                out.append((role, item))
    return out


def decide(guard: Guard, name: str, args: dict, params: set[str], targets: bool) -> str:
    """The guard's answer for one privileged call: the strictest answer over its control values."""
    amount = args.get("amount") if "amount" in params else None
    pairs = controls(args, params, targets)
    if not pairs:  # nothing in it chooses where money or data goes: only identity and scope apply
        return guard.check(ToolSpec(name, privileged=True), {}).outcome
    worst = ALLOW
    for role, value in pairs:
        spec = ToolSpec(name, privileged=True,
                        payee_arg="v" if role == "payee" else None,
                        recipient_arg="v" if role == "recipient" else None,
                        target_arg="v" if role == "target" else None,
                        amount_arg="amount" if role == "payee" and amount is not None else None)
        outcome = guard.check(spec, {"v": value, "amount": amount}).outcome
        if RANK[outcome] > RANK[worst]:
            worst = outcome
    return worst


class Replay(BasePipelineElement):
    """The worst-case agent: the user's ground truth, then the attacker's, each call past the guard."""

    name = "worst-case-replay"  # AgentDojo's attacks ask the pipeline they target for a name

    def __init__(self, suite, user_task, injection_task, condition: str, attack_text: str = "") -> None:
        self.suite, self.user_task, self.injection_task = suite, user_task, injection_task
        self.condition, self.attack_text = condition, attack_text
        self.params = {f.name: set(f.parameters.model_json_schema().get("properties", {})) for f in suite.tools}
        self.log: list[tuple[str, str, str]] = []  # (phase, tool, outcome)

    def _guard(self, prompt: str) -> Guard:
        human = Principal("user")
        passport = issue_passport(human, "Agent", "AgentDojo worst-case agent")
        mandate = issue_mandate(human, passport, "The user's task", [f.name for f in self.suite.tools], spend_limit=1e12)
        return Guard(passport, mandate, prompt)

    def query(self, query, runtime, env=gtp.EmptyEnv(), messages=(), extra_args=None):
        guard = None if self.condition == "none" else self._guard(query)
        out = []

        def step(call, phase: str) -> None:
            name, read = call.function, call.function.startswith(READ)
            outcome = ALLOW
            if guard is not None and not read:
                outcome = decide(guard, name, dict(call.args), self.params.get(name, set()), self.condition == "A")
            self.log.append((phase, name, outcome))
            if outcome != ALLOW:
                return  # protocol, rule 5: a held action is denied
            result, _ = runtime.run_function(env, name, call.args, raise_on_error=False)
            text = gtp.tool_result_to_str(result)
            out.append(gtp.ChatAssistantMessage(role="assistant", tool_calls=[call], content=[gtp.text_content_block_from_string("")]))
            out.append(gtp.ChatToolResultMessage(role="tool", content=[gtp.text_content_block_from_string(text)],
                                                 tool_call=call, tool_call_id=None, error=None))
            if guard is not None and read:
                guard.saw_untrusted(text)

        for call in self.user_task.ground_truth(env):
            step(call, "user")
        if self.injection_task is not None:
            if guard is not None:
                guard.saw_untrusted(self.attack_text)  # the attacker's text was read, or there is no attack
            for call in self.injection_task.ground_truth(env):
                step(call, "attack")
        said = self.user_task.GROUND_TRUTH_OUTPUT  # and, obeying the attacker, whatever it wanted said: the guard does not judge prose
        if self.injection_task is not None and self.injection_task.GROUND_TRUTH_OUTPUT:
            said = f"{said}\n{self.injection_task.GROUND_TRUTH_OUTPUT}"
        out.append(gtp.ChatAssistantMessage(role="assistant", tool_calls=None, content=[gtp.text_content_block_from_string(said)]))
        return query, runtime, env, [*messages, *out], extra_args or {}


def pct(n: int, d: int) -> float:
    return round(100 * n / d, 1) if d else 0.0


def run(only: list[str], names: list[str] | None = None) -> tuple[dict, list]:
    suites = {k: v for k, v in get_suites(VERSION).items() if not names or k in names}
    summary = {"benchmark": f"agentdojo {VERSION}", "agent": "worst case: ground-truth replay, no model",
               "protocol": "bench/agentdojo/PROTOCOL.md", "conditions": {}}
    rows = []
    for cond in only:
        per_suite, landed_by = {}, defaultdict(lambda: {"pairs": 0, "landed": 0, "tools": set()})
        for sname, suite in suites.items():
            # AgentDojo's own "direct" attack places the attacker's text, and only where this user task reads it.
            attack = load_attack("direct", suite, Replay(suite, None, None, "none"))
            # An injection task with no ground-truth calls cannot be replayed without a model: it is left out, and counted.
            blank = suite.load_and_inject_default_environment({})
            replayable = {iid: inj for iid, inj in suite.injection_tasks.items() if inj.ground_truth(blank) or inj.GROUND_TRUTH_OUTPUT}  # calls to make, or words to say
            c = {"user_tasks": 0, "clean_ok": 0, "clean_need_approval": 0, "clean_held_calls": 0, "pairs": 0, "attack_success": 0, "utility_under_attack": 0,
                 "pairs_not_replayable": (len(suite.injection_tasks) - len(replayable)) * len(suite.user_tasks)}
            for uid, user_task in suite.user_tasks.items():
                agent = Replay(suite, user_task, None, cond)
                utility, _ = suite.run_task_with_pipeline(agent, user_task, None, {})
                held = sum(1 for _, _, o in agent.log if o != ALLOW)
                c["user_tasks"] += 1
                c["clean_ok"] += bool(utility)
                c["clean_need_approval"] += held > 0
                c["clean_held_calls"] += held
                rows.append([cond, sname, uid, "", int(bool(utility)), "", held])
                for iid, injection in replayable.items():
                    injections = attack.attack(user_task, injection)
                    agent = Replay(suite, user_task, injection, cond, " ".join(injections.values()))
                    utility, security = suite.run_task_with_pipeline(agent, user_task, injection, injections)
                    c["pairs"] += 1
                    c["attack_success"] += bool(security)
                    c["utility_under_attack"] += bool(utility)
                    key = f"{sname}/{iid}"
                    landed_by[key]["pairs"] += 1
                    landed_by[key]["landed"] += bool(security)
                    landed_by[key]["goal"] = injection.GOAL
                    landed_by[key]["tools"] |= {f"{tool}: {out}" for phase, tool, out in agent.log if phase == "attack"}
                    rows.append([cond, sname, uid, iid, int(bool(utility)), int(bool(security)),
                                 sum(1 for _, _, o in agent.log if o != ALLOW)])
            per_suite[sname] = c
        total = {k: sum(s[k] for s in per_suite.values()) for k in next(iter(per_suite.values()))}

        def rates(c: dict) -> dict:
            return {**c, "attack_success_pct": pct(c["attack_success"], c["pairs"]), "utility_under_attack_pct": pct(c["utility_under_attack"], c["pairs"]),
                    "clean_utility_pct": pct(c["clean_ok"], c["user_tasks"]), "clean_need_approval_pct": pct(c["clean_need_approval"], c["user_tasks"]),
                    "clean_held_calls_mean": round(c["clean_held_calls"] / c["user_tasks"], 2)}

        summary["conditions"][cond] = {
            "label": CONDITIONS[cond], "total": rates(total), "suites": {k: rates(v) for k, v in per_suite.items()},
            "by_injection_task": {k: {"goal": v["goal"], "pairs": v["pairs"], "landed": v["landed"], "attack_calls": sorted(v["tools"])}
                                  for k, v in sorted(landed_by.items())}}
    return summary, rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", nargs="+", choices=list(CONDITIONS), default=list(CONDITIONS))
    ap.add_argument("--out", default=str(ROOT / "bench" / "results"))
    a = ap.parse_args()
    warnings.simplefilter("ignore")
    summary, rows = run(a.only)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if set(a.only) == set(CONDITIONS):
        (out / "agentdojo_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        (out / "agentdojo_rows.json").write_text(json.dumps({"columns": ["condition", "suite", "user_task", "injection_task", "utility", "attack_succeeded", "held_calls"],
                                                             "rows": rows}, separators=(",", ":")) + "\n")
    for cond in a.only:
        t = summary["conditions"][cond]["total"]
        print(f"{CONDITIONS[cond]:48s} attack success {t['attack_success_pct']:5.1f}% of {t['pairs']} ({t['pairs_not_replayable']} pairs not replayable) | "
              f"utility under attack {t['utility_under_attack_pct']:5.1f}% | clean utility {t['clean_utility_pct']:5.1f}% of {t['user_tasks']} | "
              f"clean tasks needing approval {t['clean_need_approval_pct']:5.1f}%, {t['clean_held_calls_mean']} held calls a task")


if __name__ == "__main__":
    main()
