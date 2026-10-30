"""The guard: four rules every privileged action must pass.

    1. Identity  - is the passport genuine, and is the mandate signed, unexpired,
                   and issued to *this* agent? For a sub-agent, does every link of
                   its delegation chain verify back to the human, unrevoked?
    2. Scope     - is this tool inside the mandate?
    3. Bounds    - is the payee, recipient or target on the mandate's list, and is
                   the amount inside the per-transaction and total budget?
    4. Provenance- if the agent has read untrusted text, did a trusted source
                   (the human's task or the mandate) choose the control values,
                   or could only the untrusted text have chosen them?

Outcomes: ALLOW, BLOCK, or ASK (pause and ask the human).

The key design choice: untrusted text may be *read*, but it can never *choose*
where money or data goes. When it can only choose an amount at a payee the human
already trusts, the mandate's budget caps the worst case, and Aurvane allows it
but labels it "bounded".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .identity import Mandate, Passport

ALLOW, BLOCK, ASK = "allow", "block", "ask"


# --- Provenance: which values came from the human, which from the wild --------

def _norm(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{float(v):g}"
    s = re.sub(r"\s+", " ", str(v)).strip().lower()
    if re.fullmatch(r"\$?\d+(\.\d+)?", s):
        return f"{float(s.lstrip('$')):g}"
    return s


def _contains(haystack: str, needle: str) -> bool:
    """Whole-token match, so "45" is not found inside "450"."""
    return re.search(r"(?<![\w.@-])" + re.escape(needle) + r"(?![\w@-])", haystack) is not None


@dataclass
class Provenance:
    trusted: list[str] = field(default_factory=list)
    untrusted: list[str] = field(default_factory=list)

    def label(self, value) -> str:
        v = _norm(value)
        if any(_contains(t, v) for t in self.trusted):
            return "trusted"
        if any(_contains(t, v) for t in self.untrusted):
            return "untrusted"
        return "unknown"


# --- Tool metadata the guard needs --------------------------------------------

@dataclass(frozen=True)
class ToolSpec:
    name: str
    privileged: bool = False          # does it change the world (pay, send, submit)?
    payee_arg: str | None = None      # checked against mandate.merchants
    recipient_arg: str | None = None  # checked against mandate.recipients
    target_arg: str | None = None     # checked against mandate.targets
    amount_arg: str | None = None     # checked against the budget
    untrusted: bool = False           # does its output come from strangers (a web page, an inbox)?


@dataclass
class Decision:
    outcome: str
    rule: str
    reason: str
    bounded: bool = False


# --- The guard ------------------------------------------------------------------

class Guard:
    def __init__(self, passport: Passport, mandate: Mandate, task_text: str, chain=None):
        self.passport = passport
        self.mandate = mandate
        self.chain = chain    # a delegation.Chain for sub-agents, None for agents the human signed directly
        self.spent = 0.0
        self.tainted = False  # has this agent read untrusted text?
        self.prov = Provenance(trusted=[_norm(task_text)])
        for v in (*mandate.merchants, *mandate.recipients, *mandate.targets):
            self.prov.trusted.append(_norm(v))

    def saw_untrusted(self, text: str) -> None:
        self.tainted = True
        self.prov.untrusted.append(_norm(text))

    def trust(self, value) -> None:
        """The human chose this value directly (for example, by tapping Allow)."""
        if value is not None:
            self.prov.trusted.append(_norm(value))

    def check(self, spec: ToolSpec, args: dict) -> Decision:
        m = self.mandate

        # 1. Identity
        if not self.passport.is_valid():
            return Decision(BLOCK, "identity", "Passport signature is invalid")
        if not m.is_valid() or m.agent_id != self.passport.agent_id:
            return Decision(BLOCK, "identity", "Mandate is invalid, expired, or not for this agent")
        if self.chain is not None and (why := self.chain.problem(self.passport, m)):
            return Decision(BLOCK, "identity", why)

        # 2. Scope
        if spec.name not in m.tools:
            return Decision(BLOCK, "scope", f"'{spec.name}' is outside the mandate")
        if not spec.privileged:
            return Decision(ALLOW, "scope", "Read-only action")

        # 3. Bounds
        for arg, allowed, what in (
            (spec.payee_arg, m.merchants, "payee"),
            (spec.recipient_arg, m.recipients, "recipient"),
            (spec.target_arg, m.targets, "target"),
        ):
            # An empty list means "not fixed in advance": provenance (rule 4) decides.
            if arg and allowed and _norm(args.get(arg, "")) not in {_norm(a) for a in allowed}:
                return Decision(BLOCK, "bounds", f"{what.capitalize()} '{args.get(arg)}' is not in the mandate")
        amount = float(args.get(spec.amount_arg, 0) or 0) if spec.amount_arg else 0.0
        if amount:
            if m.per_tx_limit and amount > m.per_tx_limit:
                return Decision(BLOCK, "bounds", f"{amount:g} {m.currency} is over the per-payment limit of {m.per_tx_limit:g}")
            if self.spent + amount > m.spend_limit:
                left = m.spend_limit - self.spent
                return Decision(BLOCK, "bounds", f"{amount:g} {m.currency} is over the {left:g} left in the budget")

        # 4. Provenance
        if self.tainted:
            for arg in (spec.payee_arg, spec.recipient_arg, spec.target_arg):
                if arg and self.prov.label(args.get(arg)) != "trusted":
                    return Decision(ASK, "provenance", f"Untrusted text may have chosen '{args.get(arg)}'")
            if amount and self.prov.label(amount) != "trusted":
                return Decision(ALLOW, "provenance",
                                "Amount came from untrusted text, but payee is trusted and the budget caps the loss",
                                bounded=True)

        return Decision(ALLOW, "bounds", "Inside the mandate")

    def commit(self, spec: ToolSpec, args: dict) -> None:
        if spec.amount_arg:
            self.spent += float(args.get(spec.amount_arg, 0) or 0)
