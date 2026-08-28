"""Meeting transcripts MCP server.

Exposes a full-text/file tool over the simulated meeting transcripts in
data/meetings/. Kept as its own MCP server (rather than a framework-specific
LangChain @tool) so the same server could be reused unchanged from any other
MCP-capable client, not just this LangGraph agent.

Run standalone for a quick manual check:
    python mcp_servers/meetings_mock_server.py
Normally it is spawned as a subprocess by langchain_mcp_adapters.
"""

from datetime import date
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

MEETINGS_DIR = Path(__file__).parent.parent / "data" / "meetings"

mcp = FastMCP("meetings-mock")


def _parse_meeting(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    _, front_matter, body = text.split("---", 2)
    meta = yaml.safe_load(front_matter)
    return {
        "filename": path.name,
        "date": meta["date"],
        "title": meta.get("title", ""),
        "participants": meta.get("participants", []),
        "body": body.strip(),
    }


def _all_meetings() -> list[dict]:
    meetings = [_parse_meeting(p) for p in sorted(MEETINGS_DIR.glob("*.md"))]
    meetings.sort(key=lambda m: m["date"])
    return meetings


@mcp.tool()
def list_meetings(date_from: str = "", date_to: str = "") -> str:
    """List available meeting transcripts, optionally filtered by date range.

    Args:
        date_from: Inclusive lower bound as YYYY-MM-DD, or "" for no bound.
        date_to: Inclusive upper bound as YYYY-MM-DD, or "" for no bound.
    """
    lo = date.fromisoformat(date_from) if date_from else date.min
    hi = date.fromisoformat(date_to) if date_to else date.max

    rows = []
    for m in _all_meetings():
        if lo <= m["date"] <= hi:
            participants = ", ".join(m["participants"])
            rows.append(f"{m['filename']} | {m['date']} | {m['title']} | {participants}")

    if not rows:
        return "Zadne mitinky v danem rozmezi nenalezeny."
    return "\n".join(rows)


@mcp.tool()
def read_meeting(filename: str) -> str:
    """Read the full transcript of one meeting by its filename.

    Args:
        filename: Exact filename as returned by list_meetings, e.g.
            "2026-07-09_sprint_planning.md".
    """
    path = MEETINGS_DIR / filename
    if not path.exists():
        return f"Soubor {filename} neexistuje."
    m = _parse_meeting(path)
    header = f"# {m['title']} ({m['date']})\nUcastnici: {', '.join(m['participants'])}\n"
    return header + "\n" + m["body"]


@mcp.tool()
def read_all_meetings(date_from: str = "", date_to: str = "") -> str:
    """Read full transcripts of all meetings in a date range, concatenated.

    Use this for broad questions like "summarize the last two weeks" where
    you need the content of several meetings at once rather than one file.

    Args:
        date_from: Inclusive lower bound as YYYY-MM-DD, or "" for no bound.
        date_to: Inclusive upper bound as YYYY-MM-DD, or "" for no bound.
    """
    lo = date.fromisoformat(date_from) if date_from else date.min
    hi = date.fromisoformat(date_to) if date_to else date.max

    chunks = []
    for m in _all_meetings():
        if lo <= m["date"] <= hi:
            header = f"# {m['title']} ({m['date']})\nUcastnici: {', '.join(m['participants'])}\n"
            chunks.append(header + "\n" + m["body"])

    if not chunks:
        return "Zadne mitinky v danem rozmezi nenalezeny."
    return "\n\n---\n\n".join(chunks)


if __name__ == "__main__":
    mcp.run()
