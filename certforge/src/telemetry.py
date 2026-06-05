"""Lightweight telemetry for CertForge.

The challenge values "telemetry, trace logs, and observability." We already
collect a per-agent `event_log` with reasoning traces and latencies in the
pipeline; this module turns that into:
  - a run summary (latency per agent, totals, mock-vs-LLM counts, loop count)
  - an append-only JSONL trace file (data/telemetry.jsonl) you can tail/inspect

It's deliberately dependency-free and OpenTelemetry-shaped in spirit (spans with
name + duration + attributes), so it could be exported to OTel later without
changing call sites.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from . import config

_TRACE_FILE = config.state_dir() / "telemetry.jsonl"


def summarize(result: dict) -> dict:
    """Build an observability summary from a completed analysis result."""
    events = result.get("event_log", [])
    spans = [e for e in events if e.get("elapsed_seconds") is not None]
    by_agent: dict[str, float] = {}
    for e in spans:
        by_agent[e["agent"]] = by_agent.get(e["agent"], 0.0) + (e["elapsed_seconds"] or 0.0)

    llm_agents = [k for k in ("AssessmentAgent", "ReadinessCritic")
                  if _powered_by_llm(result, k)]

    summary = {
        "total_agent_seconds": round(sum(by_agent.values()), 3),
        "latency_by_agent": {k: round(v, 3) for k, v in by_agent.items()},
        "agent_invocations": len(spans),
        "loop_iterations": result.get("loop_iterations_run", 1),
        "llm_powered_agents": llm_agents,
        "engine": "mock" if config.use_mock() else f"{config.LLM_PROVIDER}:{config.chat_model()}",
        "guardrail_passed": result.get("guardrail_report", {}).get("passed"),
        "verdict": result.get("critic", {}).get("verdict"),
    }
    return summary


def _powered_by_llm(result: dict, agent_key_map: str) -> bool:
    mapping = {"AssessmentAgent": "assessment", "ReadinessCritic": "critic"}
    key = mapping.get(agent_key_map)
    return key is not None and result.get(key, {}).get("powered_by") == "llm"


def record(result: dict) -> dict:
    """Append a trace record for this run to the JSONL file and return the summary."""
    summary = summarize(result)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "employee_id": result.get("learner_profile", {}).get("employee_id"),
        "certification": result.get("learner_profile", {}).get("certification"),
        **summary,
    }
    try:
        with open(_TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # read-only filesystem (e.g. hosted container) — telemetry is best-effort
    return summary


def read_traces(limit: int = 50) -> list[dict]:
    """Read the most recent telemetry records (for the UI / inspection)."""
    if not _TRACE_FILE.exists():
        return []
    lines = _TRACE_FILE.read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lines[-limit:]]


class span:
    """Context manager for timing an arbitrary block as a named span.

    Usage:
        with span("foundry_iq_query") as s:
            ...
        print(s.duration)
    """

    def __init__(self, name: str, **attrs):
        self.name = name
        self.attrs = attrs
        self.duration = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.duration = round(time.perf_counter() - self._start, 4)
        return False
