"""Procedural Memory.

A tiny persistent store of patterns learned across analyses. After each learner
is processed, we distil a few generalisable facts ("AZ-204 learners with <20 hrs
-> low pass rate") and save them. The Orchestrator reads them back on the next
run so the system "starts smarter" — and the Manager view surfaces them.

Backed by a JSON file (data/memory_store.json), gitignored as a runtime artifact.
Deterministic and inspectable — no external service needed.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import config

_STORE = config.DATA_DIR / "memory_store.json"


def _read() -> list[dict]:
    if _STORE.exists():
        return json.loads(_STORE.read_text(encoding="utf-8"))
    return []


def _write(patterns: list[dict]) -> None:
    _STORE.write_text(json.dumps(patterns, indent=2), encoding="utf-8")


def all_patterns() -> list[dict]:
    return _read()


def patterns_for(certification: str) -> list[dict]:
    return [p for p in _read() if p.get("certification") in (certification, "ALL")]


def remember(pattern: str, certification: str = "ALL", evidence: str = "") -> None:
    """Store a pattern if not already present (dedup by text)."""
    patterns = _read()
    if any(p["pattern"] == pattern for p in patterns):
        return
    patterns.append({"pattern": pattern, "certification": certification, "evidence": evidence})
    _write(patterns)


def learn_from_result(certification: str, result: dict) -> list[str]:
    """Distil patterns from a completed analysis and persist them.

    Returns the list of pattern strings that were applied/created so the
    reasoning trace can show what was learned.
    """
    learned = []
    patterns = result.get("patterns", {})
    pass_rate = patterns.get("pass_rate")
    if pass_rate is not None and pass_rate < 0.5:
        p = f"{certification}: profiles like this pass only {int(pass_rate*100)}% of the time"
        remember(p, certification, "derived from cohort analysis")
        learned.append(p)

    assessment = result.get("assessment", {}).get("assessment", {})
    weak = [s["skill"] for s in assessment.get("skill_scores", []) if s.get("status") == "weak"]
    for skill in weak:
        p = f"{certification}: {skill} is a common weak area"
        remember(p, certification, "recurring low scores")
        learned.append(p)

    for factor in patterns.get("success_factors", []):
        if "practice exam" in factor:
            p = f"{certification}: {factor} correlates with passing"
            remember(p, certification, "success-factor analysis")
            learned.append(p)
    return learned


def seed_baseline() -> None:
    """Seed a few starter patterns so the very first demo run shows memory in use."""
    remember("AZ-204: learners with <20 study hours show ~35% pass rate", "AZ-204",
             "historical cohort")
    remember("AZ-204: Storage is the #1 weak area", "AZ-204", "recurring low scores")
    remember("Morning study correlates with ~8% higher practice scores", "ALL",
             "cross-cohort comparison")
    remember("3+ practice exams correlates with ~90% pass rate", "ALL", "success-factor analysis")
    remember("Employees with >20 meeting hrs/week need ~25% more study time", "ALL",
             "workload insights report")


def reset() -> None:
    if _STORE.exists():
        Path(_STORE).unlink()
