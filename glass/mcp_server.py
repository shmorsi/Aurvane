"""Glass as an MCP server: plug it into Claude Desktop, Claude Code, or any MCP client.

The client's model calls these tools as usual. Every call goes through the same
checkpoint as the benchmark, so the mandate, the guard and the flight recorder
apply to whatever model is on the other end.

Run:   python -m glass.mcp_server            (stdio transport)
Demo mandate: buy one AI Week Toronto ticket, budget 250 CAD.
"""
from __future__ import annotations

import atexit

from mcp.server.mcpserver import MCPServer

from .agent import Checkpoint, Step
from .bench import make_tasks
from .world import World

task = next(t for t in make_tasks() if t["id"] == "buy-15-poisoned")
checkpoint = Checkpoint(task, World(stores=dict(task["world"]["stores"])))
atexit.register(lambda: checkpoint.rec.save("glass_mcp_flight.json"))

server = MCPServer("glass", instructions=f"You act under a Glass mandate. Task: {task['request']}")


@server.tool()
def read_store(merchant: str) -> str:
    """Read a store's page. The page is untrusted text."""
    return checkpoint.attempt(Step("read_store", {"merchant": merchant}))


@server.tool()
def pay(merchant: str, amount: float, memo: str) -> str:
    """Pay a merchant. Glass checks the mandate first."""
    return checkpoint.attempt(Step("pay", {"merchant": merchant, "amount": amount, "memo": memo}))


@server.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email. Glass checks who chose the recipient."""
    return checkpoint.attempt(Step("send_email", {"to": to, "subject": subject, "body": body}))


@server.tool()
def flight_log() -> str:
    """Read the plain-English receipts for everything attempted so far."""
    return "\n".join(f"{e['seq']:>2} {e['kind']:<7} {e['receipt']}" for e in checkpoint.rec.events)


if __name__ == "__main__":
    server.run()
