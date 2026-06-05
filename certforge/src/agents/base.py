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

import json
import time
from abc import ABC, abstractmethod

from .. import config, llm


class Agent(ABC):
    """Abstract base for every CertForge agent."""

    #: Human-readable name, surfaced in outputs and the trace viewer.
    name: str = "Agent"

    #: When True the agent ALWAYS uses deterministic logic, even in live mode.
    #: (Analytical agents like the Pattern Analyst want trustworthy math, not an
    #: LLM guessing at statistics.)
    deterministic: bool = False

    #: System prompt for the live LLM path. Empty -> agent stays mock-only.
    system_prompt: str = ""

    def run(self, context: dict) -> dict:
        """Execute the agent (mock or live) and stamp timing onto the result."""
        start = time.perf_counter()
        if config.use_mock():
            result = self._run_mock(context)
        else:
            result = self._run_live(context)
        result.setdefault("agent_name", self.name)
        result["elapsed_seconds"] = round(time.perf_counter() - start, 3)
        return result

    @abstractmethod
    def _run_mock(self, context: dict) -> dict:
        """Deterministic local implementation. Returns the agent's JSON output."""
        raise NotImplementedError

    # -- live (LLM) path ----------------------------------------------------
    def _run_live(self, context: dict) -> dict:
        """Run via the LLM, falling back to mock on any failure.

        Strategy: always compute the mock result first as a structurally complete
        baseline (so every key the UI/pipeline needs exists). Then let the LLM
        produce the judgment fields and merge them over the baseline. If the LLM
        errors or the agent has no prompt, we simply return the baseline.
        """
        baseline = self._run_mock(context)
        if self.deterministic or not self.system_prompt:
            return baseline
        try:
            payload = self._user_payload(context)
            llm_out = llm.chat_json(self.system_prompt, json.dumps(payload, default=str))
        except llm.LLMError as e:
            baseline.setdefault("reasoning_trace", []).append(f"(LLM unavailable, used mock: {e})")
            baseline["live_fallback"] = True
            return baseline
        return self._apply_live(baseline, llm_out, context)

    def _user_payload(self, context: dict) -> dict:
        """Data sent to the LLM as the user message. Agents override this."""
        return {"learner_profile": context.get("learner_profile", {})}

    def _apply_live(self, baseline: dict, llm_out: dict, context: dict) -> dict:
        """Merge LLM output over the mock baseline. Agents may override to validate."""
        merged = dict(baseline)
        for k, v in llm_out.items():
            if v not in (None, "", []):
                merged[k] = v
        merged["powered_by"] = "llm"
        return merged

    # -- small helpers shared by agents ------------------------------------
    @staticmethod
    def trace(*steps: str) -> list[str]:
        """Build a reasoning_trace list from positional step strings."""
        return [s for s in steps if s]
