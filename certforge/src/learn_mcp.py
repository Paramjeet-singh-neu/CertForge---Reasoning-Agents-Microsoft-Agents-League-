"""Microsoft Learn MCP client.

Connects to Microsoft's public **MS Learn MCP server** over Streamable HTTP and
calls the `microsoft_docs_search` tool to fetch real learn.microsoft.com pages
(title + URL) for a topic. This is a genuine Model Context Protocol integration —
an external tool that adds real value: the Curator cites real documentation URLs
instead of constructed ones.

Design: best-effort. One session handles many queries; any failure (offline,
timeout) returns empty results so the Curator falls back to its constructed URLs.
No auth required — MS Learn docs are public.
"""
from __future__ import annotations

import asyncio
import json
from functools import lru_cache

MCP_URL = "https://learn.microsoft.com/api/mcp"
_TIMEOUT_S = 20


async def _search_many_async(queries: tuple[str, ...], k: int) -> dict[str, list[dict]]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    out: dict[str, list[dict]] = {}
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for q in queries:
                res = await session.call_tool("microsoft_docs_search", {"query": q})
                data = json.loads(res.content[0].text) if res.content else {"results": []}
                seen, items = set(), []
                for it in data.get("results", []):
                    url = it.get("contentUrl") or it.get("url")
                    if url and url not in seen:
                        seen.add(url)
                        items.append({"title": it.get("title", "MS Learn"), "url": url})
                    if len(items) >= k:
                        break
                out[q] = items
    return out


@lru_cache(maxsize=128)
def _cached(queries: tuple[str, ...], k: int) -> tuple:
    """Run the searches once and cache by (queries, k) for the process."""
    try:
        result = asyncio.run(
            asyncio.wait_for(_search_many_async(queries, k), timeout=_TIMEOUT_S))
        return tuple((q, tuple((i["title"], i["url"]) for i in result.get(q, [])))
                     for q in queries)
    except Exception:
        return tuple((q, ()) for q in queries)


def search_many(queries: list[str], k: int = 2) -> dict[str, list[dict]]:
    """Search MS Learn for several queries at once. Returns {query: [{title,url}]}.

    Never raises — returns empty lists on any failure so callers can fall back.
    """
    cached = _cached(tuple(queries), k)
    return {q: [{"title": t, "url": u} for (t, u) in items] for q, items in cached}


def is_reachable() -> bool:
    """Quick check that the MCP server responds (used by scripts/UI)."""
    res = search_many(["azure functions"], k=1)
    return bool(res.get("azure functions"))
