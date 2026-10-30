"""Delegation chains: an agent hands a sub-agent a strictly narrower mandate.

    human --signs--> Buyer's passport and mandate
                     Buyer --signs--> Checkout's passport and a narrower mandate
                                      Checkout --signs--> ... (each link narrower again)

Anyone who knows only the human's public key can check the whole chain: every
passport and mandate is signed by the agent one step up, and every mandate is
inside its parent's on every dimension (tools, money, payees, recipients,
targets, expiry) and strictly narrower on at least one. A wider mandate fails,
whoever signed it, so text that talks a sub-agent into "asking for more" gets
nowhere: the only key that could sign more is the human's.

Two more rules keep the money honest:
  * Budget is reserved. Delegating 100 CAD moves 100 CAD from the parent's
    budget to the child's, so parent and children together never exceed what
    the human signed.
  * Revocation flows down. The human, or any agent above a mandate in its chain,
    can revoke it by signing its id; everything below that link stops at once.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, replace

from .identity import Mandate, Passport, Principal, issue_mandate, issue_passport, verify
from .world import TOOLS

LISTS = {"merchants": "payee_arg", "recipients": "recipient_arg", "targets": "target_arg"}


class DelegationRefused(ValueError):
    """The requested sub-mandate is not strictly narrower than its parent's."""


@dataclass
class Revocations:
    """Signed revocations, keyed by mandate id. Shared by everyone who verifies."""

    entries: dict[str, tuple[str, str]] = field(default_factory=dict)  # mandate_id -> (key, signature)

    def revoke(self, issuer: Principal, mandate_id: str) -> None:
        self.entries[mandate_id] = (issuer.public_key, issuer.sign({"revoke": mandate_id}))

    def revoked(self, mandate_id: str, allowed_keys: list[str]) -> bool:
        key, sig = self.entries.get(mandate_id, ("", ""))
        return key in allowed_keys and verify(key, {"revoke": mandate_id}, sig)


def wider(child: Mandate, parent: Mandate) -> str | None:
    """Why `child` is not strictly inside `parent`, or None if it is."""
    extra = sorted(set(child.tools) - set(parent.tools))
    if extra:
        return f"tools {', '.join(extra)} are not in the parent's mandate"
    if child.spend_limit > parent.spend_limit:
        return f"budget {child.spend_limit:g} is over the parent's {parent.spend_limit:g} {parent.currency}"
    if parent.per_tx_limit and child.spend_limit and not 0 < child.per_tx_limit <= parent.per_tx_limit:
        return f"per-payment limit must be at most {parent.per_tx_limit:g}"
    if child.expires_at > parent.expires_at:
        return "it expires after the parent's mandate"
    if child.currency != parent.currency:
        return "it uses a different currency"
    for k, arg in LISTS.items():
        if not any(getattr(TOOLS[t], arg, None) for t in child.tools if t in TOOLS):
            continue  # the child has no tool that uses this list, so it cannot reach past it
        p, c = set(getattr(parent, k)), set(getattr(child, k))
        if p and (not c or c - p):  # an empty list means "anyone", which is wider than a fixed list
            return f"{k} {sorted(c - p) or 'unrestricted'} are outside the parent's {sorted(p)}"
    narrower = (set(child.tools) < set(parent.tools) or child.spend_limit < parent.spend_limit
                or child.expires_at < parent.expires_at
                or (parent.per_tx_limit and child.per_tx_limit < parent.per_tx_limit)
                or any(set(getattr(child, k)) < set(getattr(parent, k)) or (getattr(child, k) and not getattr(parent, k))
                       for k in LISTS))
    return None if narrower else "it is not narrower than the parent's mandate"


@dataclass
class Chain:
    """Passports and mandates from the human down to one agent, checked link by link."""

    root_key: str                                  # the human's public key: the only thing a verifier must already trust
    links: list[tuple[Passport, Mandate]]
    revocations: Revocations = field(default_factory=Revocations)

    def problem(self, passport: Passport | None = None, mandate: Mandate | None = None,
                now: float | None = None) -> str | None:
        """None if the chain verifies. Pass the leaf the guard is enforcing, so that is what gets checked."""
        links = list(self.links)
        if passport is not None:
            links[-1] = (passport, mandate)
        keys, prev, issuer_name = [self.root_key], None, "the human"
        for p, m in links:
            issuer = keys[-1]
            if p.delegator_key != issuer or not p.is_valid():
                return f"{p.name}'s passport is not signed by {issuer_name}"
            if m.delegator_key != issuer or not m.is_valid(now) or m.agent_id != p.agent_id:
                return f"{p.name}'s mandate is not signed by {issuer_name}, or has expired"
            if prev is not None:
                if m.extra.get("parent") != prev.mandate_id:
                    return f"{p.name}'s mandate does not name its parent mandate"
                if why := wider(m, prev):
                    return f"{p.name}'s mandate is wider than its parent's: {why}"
            if self.revocations.revoked(m.mandate_id, keys):
                return f"{p.name}'s mandate was revoked"
            keys.append(p.agent_key)
            prev, issuer_name = m, p.name
        return None


def chain_of(cp) -> Chain:
    """The chain behind a checkpoint. An agent the human signed directly becomes a chain of one."""
    if cp.chain is None:
        cp.chain = cp.guard.chain = Chain(cp.passport.delegator_key, [(cp.passport, cp.mandate)])
    return cp.chain


def delegate(parent, name: str, role: str, purpose: str, tools: list[str], ttl_seconds: float | None = None,
             instruction: str = "", **limits):
    """Sign a sub-agent a narrower mandate and return its checkpoint. Raises DelegationRefused.

    `parent` is the parent's Checkpoint. The child shares the parent's world and flight
    recorder, and inherits its taint: if the parent has read untrusted text, the
    instruction it writes for the child is untrusted too.
    """
    from .agent import Checkpoint

    m_parent, chain = parent.mandate, chain_of(parent)
    remaining = m_parent.expires_at - time.time()
    ttl = remaining / 2 if ttl_seconds is None else ttl_seconds
    key = Principal(name)
    passport = issue_passport(parent.key, name, role, agent_key=key.public_key)
    mandate = issue_mandate(parent.key, passport, purpose, tools, ttl, extra={"parent": m_parent.mandate_id},
                            currency=m_parent.currency, **limits)
    child_chain = Chain(chain.root_key, chain.links + [(passport, mandate)], chain.revocations)
    why = child_chain.problem()
    left = m_parent.spend_limit - parent.guard.spent
    if why is None and mandate.spend_limit > left:
        why = f"{name}'s mandate is wider than its parent's: only {left:g} {m_parent.currency} is left to delegate"
    if why:
        parent.rec.log(parent.passport.name, "blocked", f"Refused to delegate to {name}. {why}.",
                       rule="delegation", asked=mandate.payload())
        raise DelegationRefused(why)
    parent.guard.spent += mandate.spend_limit  # reserve it: the parent can no longer spend this part
    task = {**parent.task, "id": f"{parent.task['id']}/{name}", "agent": name, "role": role, "purpose": purpose}
    child = Checkpoint(task, parent.world, parent.guarded, grant=(passport, mandate, key, child_chain), rec=parent.rec)
    child.guard.tainted = parent.guard.tainted
    child.guard.prov.untrusted = list(parent.guard.prov.untrusted)
    if instruction and parent.guard.tainted:
        child.guard.saw_untrusted(instruction)
    parent.rec.log(parent.passport.name, "delegate", f"Signed {name} a narrower mandate: {mandate.describe()}",
                   parent=m_parent.mandate_id, mandate=mandate.payload(), passport=passport.payload())
    return child


def self_signed(cp, **wider_limits) -> Mandate:
    """What a hijacked sub-agent can do on its own: sign itself a new mandate with its own key."""
    unsigned = replace(cp.mandate, delegator_key=cp.key.public_key, signature="", **wider_limits)
    return replace(unsigned, signature=cp.key.sign(unsigned.payload()))
