"""Agent 4: Engagement Agent.

Grounding: Work IQ (here, the synthetic work_signals.json).

Turns raw work signals (meeting load, focus hours, preferred slot) into:
  - recommended study windows
  - an adaptive reminder strategy
  - capacity-risk flags the Critic and Manager view rely on.

The capacity rule comes straight from the synthetic Workload Insights Report:
>20 meeting hrs/week correlates with lower study completion.
"""
from __future__ import annotations

from .. import config
from .base import Agent

HIGH_MEETING_THRESHOLD = 20
MIN_FOCUS_FOR_STUDY = 12


class EngagementAgent(Agent):
    name = "EngagementAgent"

    def _run_mock(self, context: dict) -> dict:
        profile = context["learner_profile"]
        signal = config.get_work_signal(profile["employee_id"]) or {}
        meeting = signal.get("meeting_hours_per_week", 18)
        focus = signal.get("focus_hours_per_week", 14)
        slot = signal.get("preferred_learning_slot", "Morning")
        needed = profile.get("available_hours_per_week", 6)

        # Capacity risk: high meeting load OR not enough focus headroom for study.
        if meeting > HIGH_MEETING_THRESHOLD or focus < needed + 4:
            risk = "high" if meeting > HIGH_MEETING_THRESHOLD else "medium"
        else:
            risk = "low"
        capacity_reasoning = (
            f"{focus} focus hrs available, needs {needed}/week for study; "
            f"{meeting} meeting hrs/week"
        )

        flags = []
        if risk == "high":
            flags.append("Capacity risk: recommend manager protects study time")

        windows = self._windows(slot)
        frequency = "daily" if risk != "low" else "every other day"
        reminder_schedule = self._reminders(windows, risk)

        return {
            "agent_name": self.name,
            "confidence": 0.84,
            "work_analysis": {
                "meeting_hours": meeting,
                "focus_hours": focus,
                "preferred_slot": slot,
                "capacity_risk": risk,
                "capacity_reasoning": capacity_reasoning,
            },
            "study_windows": windows,
            "reminder_strategy": {
                "frequency": frequency,
                "tone": "encouraging",
                "escalation": "If 2 sessions missed → notify manager",
            },
            "reminder_schedule": reminder_schedule,
            "flags": flags,
            "reasoning_trace": self.trace(
                f"Read Work IQ signals: {meeting} mtg hrs, {focus} focus hrs, {slot} slot",
                f"Capacity risk assessed: {risk.upper()} ({capacity_reasoning})",
                f"Recommended {len(windows)} study window(s) around focus blocks",
            f"Built {len(reminder_schedule)} adaptive reminder(s) ({risk}-risk cadence)",
            ),
        }

    def _reminders(self, windows: list[dict], risk: str) -> list[dict]:
        """Concrete reminders mapped to each study window, tone adapted to risk."""
        lead = "🔴 Protected study time —" if risk == "high" else "📚"
        out = []
        for w in windows:
            out.append({
                "day": w["day"],
                "time": w["time"],
                "channel": "Teams + calendar",
                "message": f"{lead} {w['day']} {w['time']}: focus session ({w['reasoning']}).",
            })
        if risk != "low":
            out.append({
                "day": "Friday",
                "time": "4 PM",
                "channel": "Teams",
                "message": "Weekly check-in: log your practice score and flag blockers.",
            })
        return out

    def _windows(self, slot: str) -> list[dict]:
        table = {
            "Morning": [
                {"day": "Tuesday", "time": "9-10 AM", "reasoning": "Focus block before standup"},
                {"day": "Thursday", "time": "9-10 AM", "reasoning": "Low-meeting morning"},
            ],
            "Afternoon": [
                {"day": "Monday", "time": "2-3 PM", "reasoning": "Post-lunch focus window"},
                {"day": "Wednesday", "time": "3-4 PM", "reasoning": "Light meeting afternoon"},
            ],
            "Evening": [
                {"day": "Tuesday", "time": "6-7 PM", "reasoning": "After work, no meetings"},
                {"day": "Thursday", "time": "6-7 PM", "reasoning": "Consistent evening slot"},
            ],
        }
        return table.get(slot, table["Morning"])
