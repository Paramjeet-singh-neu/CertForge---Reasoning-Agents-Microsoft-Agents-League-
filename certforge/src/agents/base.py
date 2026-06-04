"""Base agent contract for CertForge.

Every agent in the system follows the same shape:

    output = SomeAgent().run(context)

where `context` is a plain dict carrying the learner profile plus the outputs of
any upstream agents, and `output` is a JSON-serializable dict that always
includes an `agent_name` and a `reasoning_trace` list.

Why a single base class?
------------------------
1. Uniform interface -> the Orchestrator can call any agent the same way and the
   Reasoning Trace viewer can render any agent's trace the same way.
2. Mock vs. Azure swap -> each agent implements `_run_mock` now. Later we add
   `_run_azure` and the base `run` method picks which to call based on the
   CERTFORGE_MOCK flag. The pipeline code never changes.
3. Timing + trace plumbing lives here once, not copy-pasted into 9 agents.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

from .. import config


class Agent(ABC):
    """Abstract base for every CertForge agent."""

    #: Human-readable name, surfaced in outputs and the trace viewer.
    name: str = "Agent"

    def run(self, context: dict) -> dict:
        """Execute the agent and stamp timing onto the result.

        Picks the mock or Azure implementation based on config. For now only the
        mock path exists; `_run_azure` is added in the Azure integration phase.
        """
        start = time.perf_counter()
        if config.use_mock():
            result = self._run_mock(context)
        else:
            result = self._run_azure(context)
        result.setdefault("agent_name", self.name)
        result["elapsed_seconds"] = round(time.perf_counter() - start, 3)
        return result

    @abstractmethod
    def _run_mock(self, context: dict) -> dict:
        """Deterministic local implementation. Returns the agent's JSON output."""
        raise NotImplementedError

    def _run_azure(self, context: dict) -> dict:  # pragma: no cover - added later
        """Real Azure AI Foundry implementation (wired up in a later phase)."""
        raise NotImplementedError(
            f"{self.name}: Azure mode not implemented yet. Set CERTFORGE_MOCK=true."
        )

    # -- small helpers shared by agents ------------------------------------
    @staticmethod
    def trace(*steps: str) -> list[str]:
        """Build a reasoning_trace list from positional step strings."""
        return [s for s in steps if s]
