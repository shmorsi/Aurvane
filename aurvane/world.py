"""A small, fake world for agents to act in: job postings, a store, an inbox, a wallet.

Nothing here touches the real internet or real money. Every tool is either
read-only (safe to call, but its output may be untrusted text) or privileged
(it changes the world, so the guard must approve it first).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .guard import ToolSpec

TOOLS: dict[str, ToolSpec] = {
    "read_posting": ToolSpec("read_posting"),
    "read_store": ToolSpec("read_store"),
    "read_file": ToolSpec("read_file"),
    "write_draft": ToolSpec("write_draft"),
    "submit_application": ToolSpec("submit_application", privileged=True, target_arg="posting_id"),
    "send_email": ToolSpec("send_email", privileged=True, recipient_arg="to"),
    "pay": ToolSpec("pay", privileged=True, payee_arg="merchant", amount_arg="amount"),
}

# Output of these tools comes from strangers on the internet.
UNTRUSTED_SOURCES = {"read_posting", "read_store"}


class Screenshot(str):
    """Tool output that is a picture, not text: a page the agent can only *see*.

    The string itself is a short caption, which is all the guard ever reads. The
    pixels live at `.path`; a vision model gets them as an image. Aurvane does not
    need to read the picture to protect you: a value that only the picture could have
    supplied is not trusted, so rule 4 still holds it.
    """

    def __new__(cls, caption: str, path: str):
        s = super().__new__(cls, caption)
        s.path = path
        return s

    def __reduce__(self):  # keep .path through copy and pickle
        return (Screenshot, (str(self), self.path))


@dataclass
class World:
    postings: dict[str, str] = field(default_factory=dict)
    stores: dict[str, str] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=lambda: {
        "resume.md": "Sherif Morsi. CS, Concordia. Nokia AI/ML intern. Orbit multi-agent system.",
        "transcript.pdf": "PRIVATE: student ID, grades, date of birth.",
    })
    drafts: list[dict] = field(default_factory=list)
    submissions: list[dict] = field(default_factory=list)
    outbox: list[dict] = field(default_factory=list)
    payments: list[dict] = field(default_factory=list)

    def call(self, tool: str, args: dict) -> str:
        if tool == "read_posting":
            return self.postings.get(args["posting_id"], "No such posting.")
        if tool == "read_store":
            return self.stores.get(args["merchant"], "No such store.")
        if tool == "read_file":
            return self.files.get(args["path"], "No such file.")
        if tool == "write_draft":
            self.drafts.append(dict(args))
            return "Draft saved."
        if tool == "submit_application":
            self.submissions.append(dict(args))
            return f"Application submitted to {args['posting_id']}."
        if tool == "send_email":
            self.outbox.append(dict(args))
            return f"Email sent to {args['to']}."
        if tool == "pay":
            self.payments.append(dict(args))
            return f"Paid {args['amount']} to {args['merchant']}."
        raise KeyError(f"Unknown tool {tool}")
