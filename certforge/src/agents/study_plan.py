"""Agent 3: Study Plan Generator.

Grounding: Fabric IQ semantic model (recommended hours, prerequisites) plus the
Curator's module list and the Engagement Agent's capacity read.

Key behaviours:
  - allocates skills across weeks at the learner's weekly capacity
  - extends the timeline 25% when meeting load is high (synthetic workload rule)
  - on feedback-loop iterations (>1) it narrows to the Assessment's weak areas
    instead of replanning the whole curriculum (the `revision_focus` block).
"""
from __future__ import annotations

import datetime as _dt

from .. import config
from .base import Agent

HIGH_MEETING_THRESHOLD = 20


class StudyPlanGenerator(Agent):
    name = "StudyPlanGenerator"

    def _run_mock(self, context: dict) -> dict:
        profile = context["learner_profile"]
        cert = config.get_certification(profile["certification"])
        curator = context.get("curator", {})
        engagement = context.get("engagement", {})
        iteration = context.get("loop_iteration", 1)

        weekly_hours = profile.get("available_hours_per_week", 6)
        work = engagement.get("work_analysis", {})
        high_load = work.get("meeting_hours", 0) > HIGH_MEETING_THRESHOLD
        slot = work.get("preferred_slot", "Morning")

        if iteration > 1:
            return self._revision_plan(context, cert, weekly_hours, slot)

        total_hours = curator.get("total_estimated_hours", cert["recommended_hours"])
        weeks = max(1, -(-total_hours // weekly_hours))  # ceil division
        if high_load:
            weeks = round(weeks * 1.25)  # 25% longer for heavy meeting load
            total_hours = round(total_hours * 1.1)

        skills = [s["skill"] for s in curator.get("required_skills", [])] or cert["skills"]
        schedule = self._weekly_schedule(skills, weeks, weekly_hours, slot)
        target_date = (_dt.date.today() + _dt.timedelta(weeks=weeks)).isoformat()

        return {
            "agent_name": self.name,
            "confidence": 0.86,
            "loop_iteration": iteration,
            "plan": {
                "total_weeks": weeks,
                "total_hours": total_hours,
                "target_exam_date": target_date,
                "weekly_schedule": schedule,
                "milestones": [
                    {"week": max(1, weeks // 2), "target": "75% on mid-point practice"},
                    {"week": weeks, "target": "80%+ on full practice exam"},
                ],
                "revision_focus": None,
            },
            "reasoning_trace": self.trace(
                f"Fabric IQ recommends {cert['recommended_hours']} hrs for {cert['id']}",
                f"Curator effort estimate: {total_hours} hrs at {weekly_hours} hrs/week",
                f"High meeting load → +25% timeline" if high_load else "Standard timeline",
                f"Built {weeks}-week schedule targeting {slot.lower()} sessions",
            ),
        }

    def _revision_plan(self, context, cert, weekly_hours, slot) -> dict:
        """Loop iteration >1: focus only on weak areas the Assessment flagged."""
        assessment = context.get("assessment", {}).get("assessment", {})
        weak = [s["skill"] for s in assessment.get("skill_scores", []) if s.get("status") == "weak"]
        weak = weak or context.get("known_weak_areas", ["Storage"])
        add_hours = 6
        add_weeks = max(1, -(-add_hours // weekly_hours))
        schedule = self._weekly_schedule(weak, add_weeks, weekly_hours, slot)
        target_date = (_dt.date.today() + _dt.timedelta(weeks=add_weeks)).isoformat()
        return {
            "agent_name": self.name,
            "confidence": 0.85,
            "loop_iteration": context.get("loop_iteration", 2),
            "plan": {
                "total_weeks": add_weeks,
                "total_hours": add_hours,
                "target_exam_date": target_date,
                "weekly_schedule": schedule,
                "milestones": [{"week": add_weeks, "target": f"80%+ on {', '.join(weak)}"}],
                "revision_focus": {
                    "weak_areas": weak,
                    "additional_hours": add_hours,
                    "additional_weeks": add_weeks,
                    "targeted_modules": [f"{w} deep-dive" for w in weak],
                },
            },
            "reasoning_trace": self.trace(
                f"Feedback loop iteration {context.get('loop_iteration', 2)}",
                f"Narrowing plan to weak areas: {', '.join(weak)}",
                f"Added {add_hours} hrs over {add_weeks} week(s) of targeted study",
            ),
        }

    def _weekly_schedule(self, skills, weeks, weekly_hours, slot) -> list[dict]:
        schedule, n = [], max(1, weeks)
        # spread skills roughly evenly across weeks
        per_week = max(1, -(-len(skills) // n))
        for w in range(1, n + 1):
            chunk = skills[(w - 1) * per_week : w * per_week]
            if not chunk and skills:
                chunk = [skills[(w - 1) % len(skills)]]
            schedule.append(
                {
                    "week": w,
                    "focus_skills": chunk,
                    "study_hours": weekly_hours,
                    "checkpoint": f"Practice quiz target: {70 + min(w, 3) * 2}%",
                    "recommended_windows": [f"{slot} sessions per Work IQ"],
                }
            )
        return schedule
