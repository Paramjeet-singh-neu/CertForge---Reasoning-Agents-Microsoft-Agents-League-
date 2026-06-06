"""Foundry IQ client — managed Azure AI Search agentic retrieval.

Calls the knowledge base's `knowledge_base_retrieve` MCP tool (the real managed
Foundry IQ service) and returns cited extractive passages. This is the production
grounding backend; the local `knowledge/retriever.py` is the offline fallback.

Best-effort: any failure returns [] so callers degrade to local retrieval.
"""
from __future__ import annotations

import asyncio
import json
import re
from functools import lru_cache

from . import config


def _mcp_url() -> str:
    return (f"{config.FOUNDRY_IQ_ENDPOINT}/knowledgebases/{config.FOUNDRY_IQ_KB}"
            f"/mcp?api-version={config.FOUNDRY_IQ_API_VERSION}")


def _auth_headers() -> dict:
    """api-key when available (local dev); otherwise a managed-identity bearer
    token (hosted agent) — no secret baked into the container."""
    if config.FOUNDRY_IQ_KEY:
        return {"api-key": config.FOUNDRY_IQ_KEY}
    from azure.identity import (AzureCliCredential, ChainedTokenCredential,
                                DefaultAzureCredential)
    cred = ChainedTokenCredential(AzureCliCredential(), DefaultAzureCredential())
    token = cred.get_token("https://search.azure.com/.default").token
    return {"Authorization": f"Bearer {token}"}


async def _retrieve_async(queries: list[str]) -> list[dict]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(_mcp_url(), headers=_auth_headers()) as (
            read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("knowledge_base_retrieve", {"queries": queries[:3]})
            if res.isError:
                return []
            items: list[dict] = []
            for c in res.content:
                txt = getattr(c, "text", "")
                try:
                    parsed = json.loads(txt)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, list):
                    items.extend(parsed)
            return items


def _citation(content: str, query: str = "") -> str:
    """Build a 'Doc Title — Section' citation, choosing the section that best
    matches the query (KB chunks can span multiple sections)."""
    doc = re.search(r"^#\s+(.+)", content, re.M)
    doc_t = doc.group(1).strip() if doc else f"Foundry IQ: {config.FOUNDRY_IQ_KB}"
    sections = re.findall(r"^##\s+(.+?)\n(.*?)(?=^##\s+|\Z)", content, re.S | re.M)
    if not sections:
        return doc_t
    qwords = set(re.findall(r"[a-z]+", query.lower()))
    best = max(sections, key=lambda s: len(qwords & set(
        re.findall(r"[a-z]+", (s[0] + " " + s[1]).lower()))))
    return f"{doc_t} — {best[0].strip()}"


@lru_cache(maxsize=128)
def _cached(queries: tuple[str, ...], k: int) -> tuple:
    try:
        items = asyncio.run(asyncio.wait_for(_retrieve_async(list(queries)), timeout=20))
    except Exception:
        return ()
    return tuple((it.get("ref_id"), it.get("content", "")) for it in items[:k])


def search(query: str, k: int = 2) -> list[dict]:
    """Retrieve cited passages from the managed Foundry IQ knowledge base."""
    results = []
    for ref, content in _cached((query,), k):
        if not content:
            continue
        results.append({
            "citation": _citation(content, query),
            "excerpt": content[:280].strip(),
            "ref_id": ref,
            "retrieval_mode": "foundry_iq",
        })
    return results


def is_available() -> bool:
    return config.foundry_iq_enabled()
