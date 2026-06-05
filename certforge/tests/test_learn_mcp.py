"""Tests for the Microsoft Learn MCP integration in the Curator.

These are offline: they exercise the fallback path and the real-URL path by
passing module data directly, without hitting the network. A network smoke test
is provided but skipped by default.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.curator import LearningPathCurator  # noqa: E402


def test_modules_use_real_urls_when_provided():
    real = [{"title": "Azure Storage intro", "url": "https://learn.microsoft.com/azure/storage/x"},
            {"title": "Storage lab", "url": "https://learn.microsoft.com/training/storage-lab"}]
    mods = LearningPathCurator()._modules_for("Storage", "AZ-204", real)
    assert mods[0]["url"] == "https://learn.microsoft.com/azure/storage/x"
    assert mods[0]["source"] == "Microsoft Learn (MCP)"


def test_modules_fall_back_without_mcp():
    mods = LearningPathCurator()._modules_for("Storage", "AZ-204", [])
    assert all("learn.microsoft.com" in m["url"] for m in mods)
    assert mods[1]["source"] == "MS Learn (fallback)"


def test_curator_mock_mode_skips_mcp(monkeypatch):
    monkeypatch.setenv("CERTFORGE_MOCK", "true")
    import importlib
    from src import config
    importlib.reload(config)
    ctx = {"learner_profile": {"employee_id": "EMP-001", "role": "Cloud Engineer",
                               "certification": "AZ-204"}, "known_weak_areas": ["Storage"]}
    out = LearningPathCurator().run(ctx)
    assert out["learn_mcp_used"] is False  # offline-safe in mock mode


@pytest.mark.skipif(not os.getenv("RUN_NETWORK_TESTS"),
                    reason="network test; set RUN_NETWORK_TESTS=1 to enable")
def test_ms_learn_mcp_reachable():
    from src import learn_mcp
    assert learn_mcp.is_reachable()
