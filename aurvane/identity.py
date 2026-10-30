"""Agent passports and signed mandates.

A passport says *who* an agent is and which human it acts for.
A mandate says *what* that agent may do, for how long, and with how much money.
Both are signed with Ed25519, so text an agent reads can never forge or widen them.
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def canonical(obj: dict) -> bytes:
    """Deterministic JSON bytes, so a signature covers exactly one meaning."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


class Principal:
    """A human (or organisation) that holds a signing key and delegates to agents."""

    def __init__(self, name: str, key: Optional[Ed25519PrivateKey] = None):
        self.name = name
        self._key = key or Ed25519PrivateKey.generate()

    @property
    def public_key(self) -> str:
        raw = self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return _b64(raw)

    def sign(self, payload: dict) -> str:
        return _b64(self._key.sign(canonical(payload)))


def verify(public_key: str, payload: dict, signature: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(_unb64(public_key)).verify(
            _unb64(signature), canonical(payload)
        )
        return True
    except (InvalidSignature, ValueError):
        return False


@dataclass(frozen=True)
class Passport:
    """Identity of one agent, bound to the human who delegated to it."""

    agent_id: str
    name: str
    role: str
    delegator: str
    delegator_key: str
    issued_at: float
    signature: str = ""

    def payload(self) -> dict:
        d = asdict(self)
        d.pop("signature")
        return d

    def is_valid(self) -> bool:
        return verify(self.delegator_key, self.payload(), self.signature)


def issue_passport(principal: Principal, name: str, role: str) -> Passport:
    unsigned = Passport(
        agent_id=f"agt_{uuid.uuid4().hex[:10]}",
        name=name,
        role=role,
        delegator=principal.name,
        delegator_key=principal.public_key,
        issued_at=time.time(),
    )
    return Passport(**{**unsigned.payload(), "signature": principal.sign(unsigned.payload())})


@dataclass(frozen=True)
class Mandate:
    """A signed, scoped, short-lived grant of authority to one agent.

    Control values (who may be paid, who may be messaged, which postings may be
    applied to) live here, signed by the human. They are the *trusted* source
    that the guard checks an agent's privileged actions against.
    """

    mandate_id: str
    agent_id: str
    purpose: str
    tools: tuple[str, ...]
    expires_at: float
    spend_limit: float = 0.0
    per_tx_limit: float = 0.0
    currency: str = "CAD"
    merchants: tuple[str, ...] = ()
    recipients: tuple[str, ...] = ()
    targets: tuple[str, ...] = ()
    delegator_key: str = ""
    signature: str = ""
    extra: dict = field(default_factory=dict)

    def payload(self) -> dict:
        d = asdict(self)
        d.pop("signature")
        d["tools"] = list(self.tools)
        d["merchants"] = list(self.merchants)
        d["recipients"] = list(self.recipients)
        d["targets"] = list(self.targets)
        return d

    def is_valid(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return now < self.expires_at and verify(
            self.delegator_key, self.payload(), self.signature
        )

    def describe(self) -> str:
        parts = [self.purpose]
        if self.spend_limit:
            parts.append(f"spend up to {self.spend_limit:.0f} {self.currency}")
        if self.merchants:
            parts.append("at " + ", ".join(self.merchants))
        return "; ".join(parts)


def issue_mandate(
    principal: Principal,
    passport: Passport,
    purpose: str,
    tools: list[str],
    ttl_seconds: float = 3600,
    **kwargs,
) -> Mandate:
    for k in ("merchants", "recipients", "targets"):
        if k in kwargs:
            kwargs[k] = tuple(kwargs[k])
    unsigned = Mandate(
        mandate_id=f"mdt_{uuid.uuid4().hex[:10]}",
        agent_id=passport.agent_id,
        purpose=purpose,
        tools=tuple(tools),
        expires_at=time.time() + ttl_seconds,
        delegator_key=principal.public_key,
        **kwargs,
    )
    return Mandate(**{**unsigned.__dict__, "signature": principal.sign(unsigned.payload())})
