"""Run the educational agent with anonymous Parallel Search MCP tools."""

import argparse
import asyncio
import uuid
from contextlib import AsyncExitStack

from .agent import Agent
from .utils.connections import setup_mcp_connections

PARALLEL_SEARCH_SERVER = {
    "type": "streamable_http",
    "url": "https://search.parallel.ai/mcp",
    "headers": {"User-Agent": "claude-quickstarts/agents"},
}


async def search_only(objective: str) -> str:
    """Search directly through the MCP tool loader without a Claude API key."""
    async with AsyncExitStack() as stack:
        tools = await setup_mcp_connections([PARALLEL_SEARCH_SERVER], stack)
        search = next((tool for tool in tools if tool.name == "web_search"), None)
        if search is None:
            raise RuntimeError("Parallel web_search could not be loaded")
        return await search.execute(
            objective=objective,
            search_queries=[objective],
            session_id=str(uuid.uuid4()),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Question or search objective")
    parser.add_argument(
        "--search-only", action="store_true", help="Search without calling Claude"
    )
    args = parser.parse_args()
    if args.search_only:
        print(asyncio.run(search_only(args.prompt)))
        return

    session_id = str(uuid.uuid4())
    agent = Agent(
        name="WebResearcher",
        system=(
            "Research the user's question using web_search. Use web_fetch when "
            "search excerpts are insufficient. Cite source URLs in your answer. "
            f"Use session_id {session_id} for every search and fetch call."
        ),
        mcp_servers=[PARALLEL_SEARCH_SERVER],
    )
    response = agent.run(args.prompt)
    for block in response.content:
        if block.type == "text":
            print(block.text)


if __name__ == "__main__":
    main()
