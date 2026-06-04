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


PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-4o")
FOUNDRY_IQ_KB_ID = os.getenv("FOUNDRY_IQ_KB_ID", "")


# ---------------------------------------------------------------------------
# Synthetic data loaders (cached so repeated agent calls don't re-read disk)
# ---------------------------------------------------------------------------
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
