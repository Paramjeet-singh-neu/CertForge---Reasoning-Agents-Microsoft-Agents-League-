"""Agent 8: Outcome Predictor.

Produces three probability-weighted scenarios (pass / borderline / fail) grounded
in the Pattern Analyst's cohort, and a `what_if_model` that recomputes pass
probability for each adjustable lever. The What-If Simulator in the UI calls
`recompute()` directly so sliders update live without re-running the agent.
"""
from __future__ import annotations

from .. import config
from .base import Agent


class OutcomePredictor(Agent):
    name = "OutcomePredictor"

    def _run_mock(self, context: dict) -> dict:
        patterns = context.get("patterns", {})
        coeffs = patterns.get("what_if_coefficients", {})
        base = patterns.get("pass_rate", 0.45)

        # Distribute remaining probability between borderline and fail.
        pass_p = round(base, 2)
        fail_p = round(max(0.05, (1 - base) * 0.4), 2)
        border_p = round(max(0.0, 1 - pass_p - fail_p), 2)

        best, worst = self._exemplars(context["learner_profile"]["certification"])

        scenarios = {
            "pass": {
                "probability": pass_p,
                "conditions": ["Add study hours on weak areas", "Take 2 practice exams"],
                "based_on": f"Learner {best['learner_id']} (similar profile, passed after "
                            f"{best['hours_studied']} hrs)" if best else "top cohort performer",
                "timeline": "Ready in ~2 weeks with adjustments",
            },
            "borderline": {
                "probability": border_p,
                "conditions": ["Continue current pace"],
                "risk_factors": ["Weak areas still below threshold", "Few practice exams planned"],
            },
            "fail": {
                "probability": fail_p,
                "conditions": ["Study time decreases", "Weak areas not addressed"],
                "based_on": f"Learner {worst['learner_id']} ({worst['practice_score_avg']}% avg, "
                            f"{worst['hours_studied']} hrs, failed)" if worst else "cohort failures",
                "early_warnings": ["Practice scores not improving week-over-week"],
            },
        }

        what_if = self._what_if_model(base, coeffs)

        return {
            "agent_name": self.name,
            "scenarios": scenarios,
            "what_if_model": what_if,
            "what_if_coefficients": coeffs,
            "base_pass_probability": pass_p,
            "overall_recommendation": self._recommendation(pass_p, what_if),
            "reasoning_trace": self.trace(
                f"Base pass probability from cohort: {int(pass_p*100)}%",
                f"Scenarios → pass {int(pass_p*100)}% / borderline {int(border_p*100)}% "
                f"/ fail {int(fail_p*100)}%",
                "Built what-if model from Pattern Analyst coefficients",
            ),
        }

    # -- shared math so the UI and the agent agree exactly ------------------
    @staticmethod
    def recompute(base: float, coeffs: dict, *, add_hours=0, add_exams=0, morning=False) -> float:
        """Recompute pass probability for a set of lever adjustments.

        Used both to precompute the what_if_model below and live by the UI
        slider callbacks. A diminishing-returns cap keeps it sane.
        """
        delta = (
            add_hours * coeffs.get("hours_per_unit", 2.3)
            + add_exams * coeffs.get("practice_exam_per_unit", 5.0)
            + (coeffs.get("morning_switch_bonus", 8.0) if morning else 0.0)
        ) / 100.0
        # overlap discount when stacking many changes
        if sum([add_hours > 0, add_exams > 0, morning]) >= 2:
            delta *= 0.85
        return round(min(0.95, base + delta), 2)

    def _what_if_model(self, base: float, coeffs: dict) -> dict:
        def entry(p):
            return {"new_probability": p, "delta": f"+{int((p - base) * 100)}%"}
        return {
            "base_pass_probability": base,
            "adjustments": {
                "add_2_hours": entry(self.recompute(base, coeffs, add_hours=2)),
                "add_6_hours": entry(self.recompute(base, coeffs, add_hours=6)),
                "switch_to_morning": entry(self.recompute(base, coeffs, morning=True)),
                "add_2_practice_exams": entry(self.recompute(base, coeffs, add_exams=2)),
                "all_changes": entry(
                    self.recompute(base, coeffs, add_hours=6, add_exams=2, morning=True)
                ),
            },
        }

    def _recommendation(self, base: float, what_if: dict) -> str:
        best = what_if["adjustments"]["all_changes"]["new_probability"]
        return (
            f"Current pass probability {int(base*100)}%. With +6 hrs on weak areas, "
            f"2 practice exams, and morning sessions → {int(best*100)}%."
        )

    def _exemplars(self, cert: str):
        cohort = [l for l in config.learners() if l["certification"] == cert]
        passers = sorted([l for l in cohort if l["exam_outcome"] == "pass"],
                         key=lambda l: l["practice_score_avg"], reverse=True)
        failers = sorted([l for l in cohort if l["exam_outcome"] == "fail"],
                         key=lambda l: l["practice_score_avg"])
        return (passers[0] if passers else None), (failers[0] if failers else None)
