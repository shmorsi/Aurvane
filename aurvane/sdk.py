"""Aurvane for your own agent, in a few lines.

    from aurvane import Aurvane, Blocked, Held

    av = Aurvane("Buyer", may=["pay", "fetch"], budget=250, pay_to=["shop.example"], hours=1)

    @av.reads_untrusted              # its output came from strangers
    def fetch(url): ...

    @av.tool(payee="merchant", amount="amount")
    def pay(merchant, amount): ...

    pay("shop.example", 199)         # runs: inside the mandate
    pay("evil.example", 900)         # raises Blocked: not a payee you signed
    av.approve("ask_1")              # a held action runs only when you say so

Behind those lines are the same pieces the benchmark uses: a signed passport and
mandate, the four-rule guard, the hash-chained flight recorder, and approvals.
Plug the decorated functions into any agent framework or tool loop you like.
"""
from __future__ import annotations

import functools
import inspect

from .agent import Checkpoint, Step
from .guard import ToolSpec


class Blocked(PermissionError):
    """The guard refused the action. It did not run."""


class Held(PermissionError):
    """The action waits for a human. Call `approve(ask_id)` or `deny(ask_id)`."""

    def __init__(self, ask_id: str, reason: str):
        super().__init__(f"{reason} (waiting for approval: {ask_id})")
        self.ask_id = ask_id


class Aurvane:
    """One agent, one signed mandate, one flight log."""

    def __init__(self, agent: str, may: list[str], budget: float = 0.0, per_payment: float | None = None,
                 pay_to: list[str] = (), email_to: list[str] = (), targets: list[str] = (),
                 hours: float = 1.0, request: str = "", human: str = "you"):
        limits = {"spend_limit": budget, "per_tx_limit": budget if per_payment is None else per_payment,
                  "merchants": list(pay_to), "recipients": list(email_to), "targets": list(targets),
                  "ttl_seconds": hours * 3600}
        task = {"id": f"{agent}-run", "agent": agent, "role": "your agent", "human": human,
                "purpose": request.rstrip(".") or f"{agent}'s task", "request": request, "tools": list(may), "limits": limits}
        self.specs: dict[str, ToolSpec] = {}
        self.functions = {}
        self.checkpoint = Checkpoint(task, self, tools=self.specs)

    # -- registering tools ------------------------------------------------------------
    def tool(self, fn=None, *, payee: str | None = None, recipient: str | None = None,
             target: str | None = None, amount: str | None = None, untrusted: bool = False):
        """Guard a function. Name the arguments that choose where money or data goes."""
        def wrap(f):
            privileged = any((payee, recipient, target, amount))
            self.specs[f.__name__] = ToolSpec(f.__name__, privileged, payee, recipient, target, amount, untrusted)
            self.functions[f.__name__] = f
            sig = inspect.signature(f)

            @functools.wraps(f)
            def guarded(*args, **kwargs):
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                return self._attempt(f.__name__, dict(bound.arguments))
            return guarded
        return wrap(fn) if fn else wrap

    def reads_untrusted(self, fn):
        """A read-only tool whose output came from strangers: after it runs, rule 4 is on."""
        return self.tool(fn, untrusted=True)

    # -- the human's side ---------------------------------------------------------------
    def approve(self, ask_id: str):
        return self._raise_or_return(self.checkpoint.approve(ask_id))

    def deny(self, ask_id: str) -> None:
        self.checkpoint.deny(ask_id)

    @property
    def pending(self) -> dict[str, Step]:
        return dict(self.checkpoint.pending)

    def log(self) -> str:
        """The flight log as plain-English receipts, one per line."""
        return "\n".join(f"{e['seq']:>2} {e['kind']:<8} {e['receipt']}" for e in self.checkpoint.rec.events)

    def verify(self) -> bool:
        """True if no event in the log was edited or removed."""
        return self.checkpoint.rec.verify()

    # -- plumbing: the Checkpoint calls this object as its "world" -------------------------
    def call(self, tool: str, args: dict):
        return self.functions[tool](**args)

    def _attempt(self, name: str, args: dict):
        return self._raise_or_return(self.checkpoint.attempt(Step(name, args)))

    def _raise_or_return(self, out):
        last = self.checkpoint.rec.events[-1]
        if last["kind"] == "blocked":
            raise Blocked(str(out).removeprefix("Denied by Aurvane: "))
        if last["kind"] == "ask":
            raise Held(last["data"]["ask_id"], last["receipt"])
        return out
