# Lekce 8 - Agent nad mítinky s JIRA MCP nástrojem

## Zadání

Navrhnout a vytvořit agenta pomocí frameworku, který pracuje s nástroji
(tooly) a odpovídá na dotazy přes LLM. Zvolený framework: **LangGraph**.
Nástroje jsou propojené přes **MCP** (Model Context Protocol) místo
framework-specific tool wrapperů, kde to dává smysl.

## Co agent umí

Agent simuluje asistenta týmového leada, který má k dispozici přepisy
fiktivních týmových mítinků (Zoom/standup/sprint planning/klientské
konzultace) a dvě schopnosti:

1. **Automatické zakládání JIRA ticketů** - projde přepisy mítinků za dané
   období, najde místa, kde někdo explicitně říká, že se má založit ticket
   (např. *"OK, Honzo, tady na tom je založen nový ticket"*), a pro každou
   takovou zmínku zavolá `create_jira_ticket`. Nástroj běží přes **fiktivní
   JIRA MCP server** - žádná reálná JIRA se nekontaktuje. Bez nastaveného
   `MOCK_JIRA_API_TOKEN` nástroj vrátí chybu a agent ji srozumitelně předá
   uživateli, místo aby to zkoušel obejít.

2. **Odpovídání na dotazy o obsahu mítinků** - např. *"jaké je shrnutí za
   poslední dva týdny?"* - agent načte relevantní přepisy a odpoví shrnutím.

## Architektura

```
main.py                     CLI - jednorázový dotaz nebo interaktivní chat
agent/
  agent.py                  sestavení LangGraph agenta (create_react_agent)
mcp_servers/
  meetings_mock_server.py   MCP server: "File" nástroj nad přepisy mítinků
  jira_mock_server.py       MCP server: fiktivní JIRA (FastMCP, stdio)
data/meetings/*.md          simulované přepisy mítinků (2026-07-07 .. 07-20)
```

Agent je jeden ReAct-style LangGraph graf (LLM <-> tool-loop). Všech pět
nástrojů, které vidí, přichází přes **MCP** (`langchain-mcp-adapters` /
`MultiServerMCPClient`), žádný není definovaný jako framework-specific
LangChain `@tool` v kódu agenta:

- `meetings_mock_server.py` nabízí `list_meetings` / `read_meeting` /
  `read_all_meetings` - full-text nástroj nad markdown soubory (žádná DB
  není pro pár souborů potřeba)
- `jira_mock_server.py` nabízí `create_jira_ticket` / `list_jira_tickets`

`agent.py` spustí oba servery jako stdio subprocesy a přes
`client.get_tools()` dostane rovnou hotové LangChain `BaseTool` objekty pro
oba dohromady.

### Proč MCP místo framework-specific toolů

Obě sady nástrojů žijí jako samostatné MCP servery mimo kód agenta. Stejné
servery by šlo beze změny připojit i k jinému frameworku (LangChain,
Microsoft Agent Framework, Claude Desktop, ...) - logika "jak se čte
mítink" nebo "jak se zakládá JIRA ticket" je s LangGraphem provázaná jen
volně, přes protokol, ne přímo v kódu.

## Nastavení

```powershell
cd AIDevelopper/Lekce9
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Do `.env` doplň:

- `ANTHROPIC_API_KEY` - tvůj Anthropic API klíč (model: Claude Haiku 4.5,
  `claude-haiku-4-5-20251001`)
- `MOCK_JIRA_API_TOKEN` - **nech prázdné**, pokud chceš vidět, jak agent
  správně nahlásí chybějící token. Vyplň libovolnou hodnotu, pokud chceš
  vidět úspěšné (fiktivní) založení ticketu.

## Spuštění

```powershell
.venv\Scripts\python main.py
```

nebo rovnou s jedním dotazem:

```powershell
.venv\Scripts\python main.py "Projdi mitinky za posledni dva tydny a zaloz JIRA tickety, kde o tom padla zminka."
```

Ukázkové dotazy:

- `"Projdi mítinky za poslední dva týdny a založ JIRA tickety, kde o tom padla zmínka."`
  - bez `MOCK_JIRA_API_TOKEN`: agent najde zmínky (platební bug 9.7., CSV
    export pro Fjordly 15.7.) a nahlásí, že potřebuje token
  - s `MOCK_JIRA_API_TOKEN`: agent tickety skutečně (fiktivně) založí,
    zapíše je do `mcp_servers/tickets.jsonl`
- `"Jaké je shrnutí za poslední dva týdny?"`
- `"Co řešila Petra minulý týden?"`

## Simulovaná data

`data/meetings/` obsahuje 6 přepisů od 2026-07-07 do 2026-07-20 - dva
standupy, sprint planning, klientskou konzultaci a retrospektivu, s
konzistentním týmem (Honza, Petra, Tomáš, Zdeněk, Lucie, David) a dvěma
jasnými momenty založení ticketu.
