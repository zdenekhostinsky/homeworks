"""Interactive CLI for the meeting/JIRA agent.

Usage:
    python main.py
    python main.py "Projdi mitinky za posledni dva tydny a zaloz JIRA tickety."
"""

import truststore

truststore.inject_into_ssl()  # use the OS (Windows) certificate store instead
# of certifi - needed behind corporate TLS-inspecting proxies. Must run
# before any other module creates an SSL context.

import asyncio
import sys

from agent.agent import build_agent


async def run_once(agent, message: str) -> None:
    result = await agent.ainvoke({"messages": [("user", message)]})
    print(result["messages"][-1].content)


async def chat_loop(agent) -> None:
    print("Agent je pripraven. Napis dotaz (napr. 'jake je shrnuti za posledni dva tydny?'),")
    print("nebo 'konec' pro ukonceni.\n")
    history = []
    while True:
        try:
            user_input = input("Ty: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in {"konec", "exit", "quit"}:
            break
        if not user_input:
            continue
        history.append(("user", user_input))
        result = await agent.ainvoke({"messages": history})
        reply = result["messages"][-1].content
        print(f"\nAgent: {reply}\n")
        history = list(result["messages"])


async def main() -> None:
    agent = await build_agent()
    if len(sys.argv) > 1:
        await run_once(agent, " ".join(sys.argv[1:]))
    else:
        await chat_loop(agent)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    asyncio.run(main())
