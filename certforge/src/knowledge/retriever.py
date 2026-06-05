"""Knowledge retriever — the engine behind our Foundry IQ grounding layer.

This implements the Foundry IQ *pattern* (a knowledge base over approved
documents, agentic retrieval, cited answers) over the synthetic markdown docs in
certforge/knowledge/. It does real semantic retrieval:

  - documents are split into sections (chunks) by markdown headings
  - chunks are embedded once (via GitHub Models) and cached to disk
  - a query is embedded and matched by cosine similarity
  - if embeddings are unavailable (no token / offline), it falls back to a
    keyword-overlap score — so retrieval ALWAYS works for the demo

Each result carries a citation ("Document Title — Section"), so downstream agents
cite real passages instead of fabricated sources.

Provider note: in production this same interface points at an Azure AI Foundry
knowledge base (Foundry IQ over Azure AI Search). The retrieval contract is
identical; only the backend changes.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from functools import lru_cache

from .. import config, llm

_CACHE = config.state_dir() / "kb_embeddings.json"


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split a markdown doc into (section_title, body) chunks by '## ' headings."""
    parts = re.split(r"^##\s+", text, flags=re.MULTILINE)
    chunks = []
    for part in parts:
        lines = part.strip().splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        # Skip the document preamble (the leading '# Title' + disclaimer block);
        # it has no real section heading and makes a noisy citation.
        if title.startswith("#") or not body:
            continue
        chunks.append((title, body))
    return chunks


def _classify(filename: str) -> str:
    """'analytics' for aggregate reports, 'content' for study material."""
    return "analytics" if ("report" in filename or "insights" in filename) else "content"


@lru_cache(maxsize=1)
def load_chunks() -> list[dict]:
    """Load and chunk every knowledge document. Cached for the process."""
    chunks = []
    for path in sorted(config.KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        first = text.splitlines()[0] if text.splitlines() else path.stem
        doc_title = first.lstrip("# ").strip()
        kind = _classify(path.name)
        for section, body in _split_sections(text):
            chunks.append({
                "doc": doc_title,
                "file": path.name,
                "section": section,
                "kind": kind,
                "text": body,
                "citation": f"{doc_title} — {section}",
            })
    return chunks


# ---------------------------------------------------------------------------
# Embedding cache
# ---------------------------------------------------------------------------
def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_cache() -> dict:
    if _CACHE.exists():
        return json.loads(_CACHE.read_text(encoding="utf-8"))
    return {}


def _ensure_embeddings(chunks: list[dict]) -> dict | None:
    """Embed any uncached chunks (one batched call) and persist. None on failure."""
    cache = _load_cache()
    missing = [c for c in chunks if _key(c["text"]) not in cache]
    if missing:
        try:
            vectors = llm.embed([c["text"] for c in missing])
        except llm.LLMError:
            return None
        for c, v in zip(missing, vectors):
            cache[_key(c["text"])] = v
        try:
            _CACHE.write_text(json.dumps(cache), encoding="utf-8")
        except OSError:
            pass  # read-only filesystem — embeddings recomputed per process instead
    return cache


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _keyword_score(query: str, text: str) -> float:
    q = set(re.findall(r"[a-z]+", query.lower()))
    t = set(re.findall(r"[a-z]+", text.lower()))
    return len(q & t) / len(q) if q else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def search(query: str, k: int = 3, prefer_semantic: bool = True,
           kind: str | None = None) -> list[dict]:
    """Return the top-k knowledge chunks for a query, each with a citation.

    `kind` filters the knowledge base: 'content' (study material) or 'analytics'
    (aggregate reports). Study-question grounding should use 'content' so it
    doesn't accidentally cite a report's meta-commentary.

    Tries semantic (embedding) retrieval; falls back to keyword overlap.
    """
    # Managed Foundry IQ (Azure AI Search) is the production backend — use it
    # first when configured and enabled (live mode). Falls back to local on empty.
    if prefer_semantic and config.foundry_iq_enabled():
        from .. import foundry_iq
        hits = foundry_iq.search(query, k=k)
        if hits:
            return [{
                "citation": h["citation"],
                "section": h["citation"].split(" — ")[-1],
                "doc": h["citation"].split(" — ")[0],
                "excerpt": h["excerpt"],
                "score": 1.0,
                "retrieval_mode": "foundry_iq",
            } for h in hits]

    chunks = [c for c in load_chunks() if kind is None or c["kind"] == kind]
    mode = "keyword"
    scored: list[tuple[float, dict]] = []

    if prefer_semantic and llm.is_configured():
        cache = _ensure_embeddings(chunks)
        if cache is not None:
            try:
                qvec = llm.embed([query])[0]
                scored = [(_cosine(qvec, cache[_key(c["text"])]), c) for c in chunks]
                mode = "semantic"
            except llm.LLMError:
                scored = []

    if not scored:  # keyword fallback
        scored = [(_keyword_score(query, c["text"] + " " + c["section"]), c) for c in chunks]

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, c in scored[:k]:
        results.append({
            "citation": c["citation"],
            "section": c["section"],
            "doc": c["doc"],
            "excerpt": c["text"][:280],
            "score": round(score, 3),
            "retrieval_mode": mode,
        })
    return results


def citations_for(query: str, k: int = 3) -> list[str]:
    """Convenience: just the citation strings for a query."""
    return [r["citation"] for r in search(query, k=k)]
