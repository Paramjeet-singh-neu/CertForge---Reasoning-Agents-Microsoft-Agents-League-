"""Agent 1: Orchestrator (Planner + Loop Controller).

Grounding: Procedural Memory.

The Orchestrator does the *planning* half of the planner-executor pattern: it
reads learned patterns, builds the learner profile, and decides the subtasks.
The actual *execution* (running agents, sequencing, looping) lives in
pipeline/runner.py — separating "what to do" from "doing it" keeps each testable.
"""
from __future__ import annotations

from .. import config
from ..memory import procedural_memory
from .base import Agent

MAX_LOOPS = 3


class Orchestrator(Agent):
    name = "Orchestrator"

    def _run_mock(self, context: dict) -> dict:
        profile = context["learner_profile"]
        cert = profile["certification"]

        # 1. Recall patterns from previous learners.
        memory = procedural_memory.patterns_for(cert)
        applied = [m["pattern"] for m in memory[:3]]

        # 2. Enrich the profile from data so downstream agents share one source.
        learner = config.get_learner(profile["employee_id"]) or {}
        signal = config.get_work_signal(profile["employee_id"]) or {}
        role = config.get_role(profile.get("role", "")) or {}

        enriched = {
            **profile,
            "weak_areas": learner.get("weak_areas", []),
            "team": signal.get("team"),
            "manager": signal.get("manager"),
            "career_path": role.get("career_path", [cert]),
        }

        # 3. Decompose into the parallel subtasks.
        subtasks = [
            {"agent": "LearningPathCurator", "goal": "Map cert to cited modules"},
            {"agent": "StudyPlanGenerator", "goal": "Build capacity-aware schedule"},
            {"agent": "EngagementAgent", "goal": "Find study windows from work signals"},
            {"agent": "PerformancePatternAnalyst", "goal": "Find pass/fail patterns"},
        ]

        return {
            "agent_name": self.name,
            "learner_profile": enriched,
            "memory_patterns_applied": applied,
            "parallel_subtasks": subtasks,
            "loop_iteration": context.get("loop_iteration", 1),
            "max_loops": MAX_LOOPS,
            "reasoning_trace": self.trace(
                f"Recalled {len(memory)} memory pattern(s) for {cert}; applied {len(applied)}",
                f"Built profile for {profile['employee_id']} ({profile.get('role')})",
                f"Decomposed into {len(subtasks)} parallel subtasks",
            ),
        }
