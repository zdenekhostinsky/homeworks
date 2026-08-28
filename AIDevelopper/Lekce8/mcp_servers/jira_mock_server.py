"""Fictitious JIRA MCP server.

This server never talks to a real Atlassian instance. It exists purely to
demonstrate an agent calling an external tool through MCP and handling a
missing-credentials failure gracefully. Tickets it "creates" are appended to
a local JSON file (tickets.json, next to this script) so the effect of a
successful call is still visible.

Run standalone for a quick manual check:
    python mcp_servers/jira_mock_server.py
Normally it is spawned as a subprocess by langchain_mcp_adapters.
"""

import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from filelock import FileLock
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

load_dotenv(override=True)

# One JSON object per line (JSON Lines), not a single JSON array. Each
# create_jira_ticket call runs in its own subprocess with no shared state, and
# a plain OS-level append is not enough on its own: when two subprocesses
# write concurrently (the agent can fire several tool calls in parallel),
# their writes can still interleave mid-line. FileLock serializes access
# across processes so appends never tear.
TICKETS_FILE = Path(__file__).parent / "tickets.jsonl"
LOCK_FILE = TICKETS_FILE.with_suffix(".lock")

mcp = FastMCP("jira-mock")


def _load_tickets() -> list[dict]:
    if not TICKETS_FILE.exists():
        return []
    lines = TICKETS_FILE.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _append_ticket(ticket: dict) -> None:
    with FileLock(str(LOCK_FILE)):
        with TICKETS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ticket, ensure_ascii=False) + "\n")


@mcp.tool()
def create_jira_ticket(summary: str, description: str, reporter: str = "") -> str:
    """Create a JIRA ticket (fictitious - no real JIRA instance is contacted).

    Args:
        summary: Short one-line ticket title.
        description: Full ticket description with relevant context.
        reporter: Who raised the underlying request (optional).
    """
    token = os.environ.get("MOCK_JIRA_API_TOKEN")
    if not token:
        raise ToolError(
            "MOCK_JIRA_API_TOKEN není nastaven. Pro založení JIRA ticketu "
            "potřebuji platný token - doplň MOCK_JIRA_API_TOKEN do .env a "
            "zkus to znovu."
        )

    ticket_id = f"PROJ-{uuid.uuid4().hex[:4].upper()}"
    ticket = {
        "id": ticket_id,
        "summary": summary,
        "description": description,
        "reporter": reporter,
    }
    _append_ticket(ticket)

    return f"Ticket {ticket_id} vytvořen: {summary}"


@mcp.tool()
def list_jira_tickets() -> str:
    """List all fictitious JIRA tickets created so far in this demo."""
    tickets = _load_tickets()
    if not tickets:
        return "Zatím nebyl vytvořen žádný ticket."
    lines = [f"{t['id']}: {t['summary']}" for t in tickets]
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
