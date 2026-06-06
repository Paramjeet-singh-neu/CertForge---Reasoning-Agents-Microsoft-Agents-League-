"""Work IQ layer — organizational work-context signals.

Work IQ is Microsoft's workplace-intelligence layer (meeting load, focus time,
collaboration patterns) that personalises agents to how work actually happens.
The Engagement Agent and Manager Insights consume this layer to adapt study
windows, capacity decisions, and reminders.

Data source: **synthetic** work signals (`data/work_signals.json`). The challenge
mandates synthetic data only (no real PII), so we deliberately do NOT connect the
managed Work IQ service, which reads real Microsoft 365 tenant data (emails,
meetings, chats). In production this module swaps to the **Work IQ API /
Microsoft Graph** behind the same `get_work_context()` interface — no agent
changes — exactly like our LLM and Foundry IQ provider swaps.
"""
from __future__ import annotations

from . import config

HIGH_MEETING = 20
LOW_MEETING = 14
MIN_FOCUS = 12


def get_work_context(employee_id: str) -> dict:
    """Return the Work IQ context for an employee: raw signals + derived insights."""
    sig = config.get_work_signal(employee_id) or {}
    meeting = sig.get("meeting_hours_per_week", 18)
    focus = sig.get("focus_hours_per_week", 14)
    slot = sig.get("preferred_learning_slot", "Morning")

    collaboration_load = ("high" if meeting > HIGH_MEETING
                          else "moderate" if meeting >= LOW_MEETING else "low")
    availability = "constrained" if focus < MIN_FOCUS else "healthy"

    return {
        "employee_id": employee_id,
        "meeting_hours_per_week": meeting,
        "focus_hours_per_week": focus,
        "preferred_learning_slot": slot,
        "team": sig.get("team"),
        "manager": sig.get("manager"),
        # Derived Work IQ insights (the "context" layer):
        "collaboration_load": collaboration_load,
        "availability": availability,
        "flow_of_work_note": _flow_note(meeting, focus, slot),
        "source": "synthetic work signals (production: Work IQ API / Microsoft Graph)",
    }


def _flow_note(meeting: float, focus: float, slot: str) -> str:
    if meeting > HIGH_MEETING:
        return (f"Heavy collaboration ({meeting} mtg hrs/wk) leaves little focus room — "
                f"protect {slot.lower()} blocks and extend the timeline.")
    if focus >= 15:
        return f"Strong focus capacity ({focus} hrs/wk) — can accelerate in {slot.lower()} slots."
    return f"Balanced load — schedule study in {slot.lower()} focus windows."
