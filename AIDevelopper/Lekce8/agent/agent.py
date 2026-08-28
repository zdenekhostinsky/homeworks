"""Builds the LangGraph agent: Claude Haiku + two fictitious MCP servers
(meetings, JIRA). All tools are supplied via MCP - none are framework-
specific LangChain @tool wrappers.
"""

import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

load_dotenv(override=True)  # .env wins even if a stale ANTHROPIC_API_KEY
# already exists in the shell/system environment.

MCP_SERVERS_DIR = Path(__file__).parent.parent / "mcp_servers"
MEETINGS_SERVER_SCRIPT = MCP_SERVERS_DIR / "meetings_mock_server.py"
JIRA_SERVER_SCRIPT = MCP_SERVERS_DIR / "jira_mock_server.py"

MODEL_NAME = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = f"""Jsi asistent týmového leada. Máš přístup k přepisům týmových
mítinků (standupy, sprint planningy, konzultace s klienty) a k nástroji pro
založení JIRA ticketu.

Dnešní datum je {date.today().isoformat()}.

Tvoje dvě hlavní schopnosti:

1. Procházení mítinků a zakládání JIRA ticketů: když uživatel požádá o
   prohledání mítinků a založení ticketů za nějaké období, načti přepisy
   pomocí list_meetings/read_all_meetings a najdi místa, kde někdo explicitně
   říká, že se má založit ticket (např. "založ na to ticket", "OK, tady na
   tom je založen nový ticket"). Pro každou takovou zmínku zavolej
   create_jira_ticket s výstižným summary a description, které shrnuje
   kontext z konverzace (kdo o co žádal, proč, případné detaily). Pokud
   nástroj selže kvůli chybějícímu tokenu, tuto chybu uživateli srozumitelně
   vysvětli a nezkoušej to obcházet.

2. Odpovídání na dotazy o obsahu mítinků (např. "jaké je shrnutí za poslední
   dva týdny"): použij read_all_meetings s příslušným datovým rozsahem a
   odpověz stručným shrnutím v češtině.

Vždy pracuj s reálným obsahem přepisů získaným přes nástroje, nevymýšlej si
informace o mítincích.
"""


def _mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "meetings": {
                "command": sys.executable,
                "args": [str(MEETINGS_SERVER_SCRIPT)],
                "transport": "stdio",
            },
            "jira_mock": {
                "command": sys.executable,
                "args": [str(JIRA_SERVER_SCRIPT)],
                "transport": "stdio",
                "env": {
                    "MOCK_JIRA_API_TOKEN": os.environ.get("MOCK_JIRA_API_TOKEN", ""),
                },
            },
        }
    )


async def build_agent():
    client = _mcp_client()
    tools = await client.get_tools()
    model = ChatAnthropic(model=MODEL_NAME, temperature=0)
    return create_react_agent(model, tools, prompt=SYSTEM_PROMPT)
