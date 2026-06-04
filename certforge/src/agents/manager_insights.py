"""Manager Insights Agent (Synthesizer).

Grounding: Work IQ (capacity) + Fabric IQ (semantic team/role structure).

Two modes:
  - individual(result): a per-learner readiness summary + gamification.
  - team(results): aggregates a batch of learner results into a risk heatmap,
    pattern insights, and recommended manager actions for the team dashboard.

Privacy note (Responsible AI): team output reports readiness/risk, not raw
practice answers or sensitive personal detail.
"""
from __future__ import annotations

from statistics import mean

from .. import config
from ..memory import procedural_memory
from .base import Agent


class ManagerInsightsAgent(Agent):
    name = "ManagerInsightsAgent"

    def _run_mock(self, context: dict) -> dict:
        if context.get("mode") == "team":
            return self._team(context["results"])
        return self._individual(context["result"])

    # -- individual ---------------------------------------------------------
    def _individual(self, result: dict) -> dict:
        a = result.get("assessment", {}).get("assessment", {})
        overall = a.get("overall_score", 0)
        skills = a.get("skill_scores", [])
        percentile = self._percentile(result["learner_profile"]["certification"], overall)
        return {
            "agent_name": self.name,
            "view": "individual",
            "readiness": {
                "overall_score": overall,
                "status": a.get("readiness_status"),
                "verdict": result.get("critic", {}).get("verdict"),
                "loop_iterations": result.get("loop_iteration", 1),
            },
            "gamification": {
                "study_streak_days": 12,
                "percentile": percentile,
                "skill_badges": {
                    s["skill"]: ("⭐⭐⭐" if s["status"] == "strong"
                                 else "⭐⭐" if s["status"] == "adequate" else "⭐")
                    for s in skills
                },
            },
            "reasoning_trace": self.trace(
                f"Synthesised individual report: {overall}% ({a.get('readiness_status')})",
                f"Percentile vs cohort: {percentile}th",
            ),
        }

    # -- team ---------------------------------------------------------------
    def _team(self, results: list[dict]) -> dict:
        rows, alerts = [], []
        for r in results:
            prof = r["learner_profile"]
            risk = self._risk(r)
            # Report current (pre-intervention) standing, plus where the plan lands.
            rows.append({
                "employee_id": prof["employee_id"],
                "certification": prof["certification"],
                "score": r.get("initial_score", 0),
                "status": r.get("initial_status"),
                "risk": risk,
                "loops_to_ready": r.get("loop_iterations_run", 1),
                "projected_status": r.get("assessment", {}).get("assessment", {}).get("readiness_status"),
            })
            sig = config.get_work_signal(prof["employee_id"]) or {}
            if sig.get("meeting_hours_per_week", 0) > 22:
                alerts.append(f"{prof['employee_id']}: {sig['meeting_hours_per_week']} "
                              f"meeting hrs/week — CRITICAL capacity")

        ready = sum(1 for row in rows if row["status"] == "ready")
        team_pass = round(mean([r.get("initial_pass_rate", self._row_pass(r))
                                for r in results]), 2) if results else 0
        if team_pass < 0.8:
            alerts.append(f"Team pass prediction {int(team_pass*100)}% — below 80% target")

        return {
            "agent_name": self.name,
            "view": "team",
            "risk_heatmap": rows,
            "team_readiness": f"{ready}/{len(rows)} Ready",
            "team_pass_prediction": team_pass,
            "alerts": alerts,
            "pattern_insights": [m["pattern"] for m in procedural_memory.all_patterns()[:5]],
            "recommended_actions": self._actions(rows, alerts),
            "memory_insight": (
                "Across analysed learners, the strongest predictors of success are "
                "practice-exam count and total study hours."
            ),
            "reasoning_trace": self.trace(
                f"Aggregated {len(rows)} learners; {ready} ready",
                f"Team pass prediction: {int(team_pass*100)}%",
                f"Raised {len(alerts)} risk alert(s)",
            ),
        }

    # -- helpers ------------------------------------------------------------
    def _risk(self, result: dict) -> str:
        """Risk reflects the learner's real, pre-intervention standing.

        A learner already at/above threshold can't be HIGH risk even if peers
        historically struggled — that's MEDIUM (caution), not HIGH.
        """
        verdict = result.get("initial_verdict", result.get("critic", {}).get("verdict"))
        status = result.get("initial_status")
        if verdict == "READY":
            return "low"
        if verdict == "CRITICAL_GAPS":
            return "medium" if status == "ready" else "high"
        return "medium"

    def _row_pass(self, result: dict) -> float:
        return result.get("predictor", {}).get("base_pass_probability",
                                                result.get("patterns", {}).get("pass_rate", 0.5))

    def _percentile(self, cert: str, score: int) -> int:
        cohort = [l["practice_score_avg"] for l in config.learners() if l["certification"] == cert]
        if not cohort:
            return 50
        below = sum(1 for s in cohort if s < score)
        return round(below / len(cohort) * 100)

    def _actions(self, rows, alerts) -> list[str]:
        actions = []
        at_risk = [r["employee_id"] for r in rows if r["risk"] != "low"]
        if at_risk:
            actions.append(f"Protect 4 hrs/week study time for {', '.join(at_risk)}")
        actions.append("Schedule a team workshop on the most common weak area")
        actions.append("Require 2 practice exams before exam scheduling")
        return actions
