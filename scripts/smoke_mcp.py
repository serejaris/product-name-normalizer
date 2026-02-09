#!/usr/bin/env python3
"""
Smoke test for the MCP server (stdio transport).

This spawns the server process and calls its tools via the official MCP Python client.
It is safe to run locally: it uses a temporary terms file via TERM_FIXER_TERMS_PATH.

Run:
  uv run python scripts/smoke_mcp.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import anyio

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult


def _result_text(result: CallToolResult) -> str:
    parts: list[str] = []
    for item in result.content:
        if getattr(item, "type", None) == "text":
            parts.append(getattr(item, "text", ""))
    return "".join(parts)


async def _main() -> None:
    with tempfile.TemporaryDirectory() as td:
        terms_path = Path(td) / "product-terms.json"

        server = StdioServerParameters(
            command="uv",
            args=["-q", "--directory", str(Path(__file__).resolve().parents[1]), "run", "term_fixer.py"],
            env={
                # Ensure we don't touch real user data when smoke-testing.
                "TERM_FIXER_TERMS_PATH": str(terms_path),
            },
        )

        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                tool_names = sorted(t.name for t in tools.tools)
                print("tools:", tool_names)

                res1 = await session.call_tool("fix_terms", {"text": "Cloudcode vs Wisprflow and Antygravity"})
                print("fix_terms:", _result_text(res1))

                res2 = await session.call_tool("add_term", {"correct": "FooBar", "wrong_variants": ["Foobar"]})
                print("add_term:", _result_text(res2) or (res2.structuredContent or ""))

                res3 = await session.call_tool("fix_terms", {"text": "i like foobar"})
                print("fix_terms(after add):", _result_text(res3))

                assert terms_path.exists(), "terms file wasn't created"
                assert _result_text(res1) == "Claude Code vs Wispr Flow and Antigravity"
                assert _result_text(res3) == "i like FooBar"


if __name__ == "__main__":
    # Default backend is asyncio (no extra deps). Trio is not required.
    anyio.run(_main)
