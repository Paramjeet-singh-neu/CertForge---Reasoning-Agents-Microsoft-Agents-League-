"""Central configuration and data loading for CertForge.

Everything that touches the filesystem or environment lives here so the rest of
the code never hardcodes paths or reads os.environ directly. This keeps the
agents pure (data in -> JSON out) and easy to test.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Project layout: <repo>/certforge/src/config.py -> PROJECT_ROOT = <repo>/certforge
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"

# Load .env from the certforge folder if present (never committed).
load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------------------------
# Environment / Azure settings
# ---------------------------------------------------------------------------
def use_mock() -> bool:
    """When true, agents run with local deterministic logic (no Azure calls).

    This lets the whole pipeline + UI run on a laptop while an Azure resource is
    still provisioning, and guarantees a demo-safe fallback.
    """
    return os.getenv("CERTFORGE_MOCK", "true").lower() == "true"


# --- LLM provider (live mode) ---------------------------------------------
# We default to GitHub Models (free, no Azure quota/region walls). The agents
# don't care which provider answers — they just need a JSON-capable chat model.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "github")  # "github" | "azure"
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "openai/text-embedding-3-small")
# Foundry (azure provider) model names — bare ids for Instant Models (no deployment).
AZURE_MODEL = os.getenv("AZURE_MODEL", "gpt-4.1-mini")
AZURE_EMBED_MODEL = os.getenv("AZURE_EMBED_MODEL", "text-embedding-3-small")


def chat_model() -> str:
    return AZURE_MODEL if LLM_PROVIDER == "azure" else LLM_MODEL


def embed_model() -> str:
    return AZURE_EMBED_MODEL if LLM_PROVIDER == "azure" else EMBED_MODEL
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_MODELS_ENDPOINT = os.getenv("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference")

# --- Azure AI Foundry (optional; for Foundry IQ knowledge layer) -----------
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-4o-mini")
FOUNDRY_IQ_KB_ID = os.getenv("FOUNDRY_IQ_KB_ID", "")

# --- Foundry IQ knowledge base (managed Azure AI Search agentic retrieval) ---
FOUNDRY_IQ_ENDPOINT = os.getenv("FOUNDRY_IQ_ENDPOINT", "")   # https://<svc>.search.windows.net
FOUNDRY_IQ_KB = os.getenv("FOUNDRY_IQ_KB", "")               # knowledge base name
FOUNDRY_IQ_KEY = os.getenv("FOUNDRY_IQ_KEY", "")             # search api-key (secret)
FOUNDRY_IQ_API_VERSION = os.getenv("FOUNDRY_IQ_API_VERSION", "2026-05-01-preview")


def foundry_iq_enabled() -> bool:
    # Enabled with an api-key (local dev) OR via managed identity (hosted agent:
    # endpoint + kb present, auth comes from the agent's Entra identity).
    return bool(FOUNDRY_IQ_ENDPOINT and FOUNDRY_IQ_KB)


# ---------------------------------------------------------------------------
# Synthetic data loaders (cached so repeated agent calls don't re-read disk)
# ---------------------------------------------------------------------------
def state_dir() -> Path:
    """Writable directory for runtime artifacts (memory, telemetry, embedding cache).

    Defaults to the data dir for local dev, but in a read-only hosted container
    (Foundry Agent Service) set CERTFORGE_STATE_DIR to a writable path (e.g. /tmp).
    """
    d = Path(os.getenv("CERTFORGE_STATE_DIR", str(DATA_DIR)))
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def _load_json(name: str):
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def learners() -> list[dict]:
    """Historical learner records — the basis for pattern analysis."""
    return _load_json("learners.json")


@lru_cache(maxsize=1)
def work_signals() -> list[dict]:
    """Synthetic Work IQ signals (meeting/focus hours, preferred slot, team)."""
    return _load_json("work_signals.json")


@lru_cache(maxsize=1)
def semantic_model() -> dict:
    """Fabric IQ semantic layer: role -> cert -> skills -> hours -> threshold."""
    return _load_json("semantic_model.json")


# ---------------------------------------------------------------------------
# Convenience lookups over the semantic model / data
# ---------------------------------------------------------------------------
def get_certification(cert_id: str) -> dict | None:
    return next((c for c in semantic_model()["certifications"] if c["id"] == cert_id), None)


def get_role(role_name: str) -> dict | None:
    return next((r for r in semantic_model()["roles"] if r["role"] == role_name), None)


def get_work_signal(employee_id: str) -> dict | None:
    return next((w for w in work_signals() if w["employee_id"] == employee_id), None)


def get_learner(employee_id: str) -> dict | None:
    return next((l for l in learners() if l["employee_id"] == employee_id), None)
