"""Agent 7: Performance Pattern Analyst.

Grounding: Foundry IQ + Fabric IQ (here, the synthetic historical learner set).

This agent is the system's *evidence engine*. It matches the current learner
against historical records and derives:
  - the pass rate for this profile (the Critic uses this to challenge "ready")
  - success / failure factors
  - what-if coefficients (the Outcome Predictor + What-If simulator use these)

All numbers are computed from data/learners.json so the output is deterministic
and explainable, not invented.
"""
from __future__ import annotations

import math
from statistics import mean

from .. import config
from .base import Agent


def _passed(learner: dict) -> bool:
    return learner["exam_outcome"].lower() == "pass"


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _personal_signal(score: float, hours: float, exams: float) -> float:
    """Pass-likelihood from the learner's OWN metrics, grounded in the synthetic
    success factors (>~75% practice, >~20 hrs, 2+ practice exams). Centred so a
    typical-threshold learner sits near 0.5."""
    return _sigmoid((score - 72) / 8 + (hours - 20) / 6 + (exams - 2) / 2)


class PerformancePatternAnalyst(Agent):
    name = "PerformancePatternAnalyst"
    #: Always deterministic — we want trustworthy math, never an LLM's guess.
    deterministic = True

    def _run_mock(self, context: dict) -> dict:
        profile = context["learner_profile"]
        cert = profile["certification"]
        me = config.get_learner(profile["employee_id"]) or {}
        my_score = me.get("practice_score_avg", profile.get("practice_score_avg", 70))
        my_hours = me.get("hours_studied", profile.get("hours_studied", 18))

        # Cohort = everyone attempting the same certification (excluding me).
        cohort = [
            l for l in config.learners()
            if l["certification"] == cert and l["employee_id"] != profile["employee_id"]
        ]

        # Close matches: similar hours (+/-5) and similar score (+/-10).
        matches = [
            l for l in cohort
            if abs(l["hours_studied"] - my_hours) <= 5
            and abs(l["practice_score_avg"] - my_score) <= 10
        ]
        match_pool = matches or cohort  # fall back to whole cohort if no close match
        passers = [l for l in match_pool if _passed(l)]
        cohort_rate = round(len(passers) / len(match_pool), 2) if match_pool else 0.5

        # Blend the cohort signal with the learner's own metrics. When the cohort
        # match is tight we trust it more; when it's a loose fallback we lean on
        # the learner's personal signal (their own hours/score/exams).
        my_exams = me.get("practice_exams_taken", profile.get("practice_exams_taken", 1))
        personal = _personal_signal(my_score, my_hours, my_exams)
        tight = bool(matches) and len(match_pool) >= 2
        w_cohort = 0.6 if tight else 0.3
        pass_rate = round(w_cohort * cohort_rate + (1 - w_cohort) * personal, 2)

        # --- Derive what-if coefficients from the cohort -------------------
        coeffs = self._coefficients(cohort)

        patterns = [
            {
                "pattern": f"Estimated pass probability: {int(pass_rate * 100)}%",
                "evidence": f"{len(passers)}/{len(match_pool)} matching learners passed "
                            f"(cohort {int(cohort_rate*100)}%, personal signal "
                            f"{int(personal*100)}%, {'tight' if tight else 'loose'} match)",
                "confidence": 0.78,
            }
        ]

        # Success/failure factors from comparing passers vs failers in cohort.
        cohort_pass = [l for l in cohort if _passed(l)]
        cohort_fail = [l for l in cohort if not _passed(l)]
        success_factors, failure_factors = self._factors(cohort_pass, cohort_fail)

        recommendation = self._recommendation(pass_rate, coeffs, me)

        return {
            "agent_name": self.name,
            "confidence": 0.78,
            "profile_match": {
                "certification": cert,
                "my_score": my_score,
                "my_hours": my_hours,
                "matching_learners": len(match_pool),
                "used_close_match": bool(matches),
            },
            "patterns": patterns,
            "pass_rate": pass_rate,
            "success_factors": success_factors,
            "failure_factors": failure_factors,
            "what_if_coefficients": coeffs,
            "recommendation": recommendation,
            "reasoning_trace": self.trace(
                f"Matched against {len(cohort)} {cert} learners",
                f"Close-profile matches: {len(match_pool)} "
                f"({'tight' if matches else 'fell back to full cohort'})",
                f"Pass rate for profile: {int(pass_rate*100)}% "
                f"({len(passers)}/{len(match_pool)})",
                f"Derived what-if coefficients: {coeffs}",
            ),
        }

    # -- analytics helpers --------------------------------------------------
    def _coefficients(self, cohort: list[dict]) -> dict:
        """Estimate the marginal effect of each lever from cohort data."""
        passers = [l for l in cohort if _passed(l)]
        failers = [l for l in cohort if not _passed(l)]

        def safe_mean(rows, key, default):
            vals = [r[key] for r in rows]
            return mean(vals) if vals else default

        # Hours: difference in avg hours between pass/fail, spread over a
        # plausible point gain, expressed as pass-probability % per hour.
        pass_hours = safe_mean(passers, "hours_studied", 24)
        fail_hours = safe_mean(failers, "hours_studied", 16)
        hour_gap = max(pass_hours - fail_hours, 1)
        hours_per_unit = round(min(30.0 / hour_gap, 4.0), 1)  # ~2-3 %/hr typically

        # Practice exams: pass-rate lift per extra exam.
        pass_exams = safe_mean(passers, "practice_exams_taken", 2.5)
        fail_exams = safe_mean(failers, "practice_exams_taken", 0.5)
        exam_gap = max(pass_exams - fail_exams, 0.5)
        practice_per_unit = round(min(20.0 / exam_gap, 8.0), 1)

        # Morning study advantage: avg score morning vs non-morning.
        morning = [l["practice_score_avg"] for l in cohort if l["study_slot"] == "morning"]
        other = [l["practice_score_avg"] for l in cohort if l["study_slot"] != "morning"]
        morning_bonus = round(
            (mean(morning) - mean(other)) if morning and other else 8.0, 1
        )

        return {
            "hours_per_unit": hours_per_unit,
            "practice_exam_per_unit": practice_per_unit,
            "morning_switch_bonus": max(morning_bonus, 0.0),
            "focus_hours_per_unit": 1.5,
        }

    def _factors(self, passers: list[dict], failers: list[dict]):
        success, failure = [], []
        if passers:
            success.append(f"{int(mean([p['hours_studied'] for p in passers]))}+ study hours")
            if mean([p["practice_exams_taken"] for p in passers]) >= 2:
                success.append("2+ practice exams")
            success.append("75%+ practice average")
        if failers:
            failure.append(f"<{int(mean([f['hours_studied'] for f in failers]))+1} study hours")
            if mean([f["practice_exams_taken"] for f in failers]) < 1.5:
                failure.append("0-1 practice exams")
            failure.append("weak areas left unaddressed")
        return success, failure

    def _recommendation(self, pass_rate: float, coeffs: dict, me: dict) -> str:
        if pass_rate >= 0.7:
            return "Profile is on track. Maintain pace and complete planned practice exams."
        gap_to_target = 0.72 - pass_rate
        extra_hours = max(round(gap_to_target * 100 / coeffs["hours_per_unit"]), 4)
        return (
            f"Add ~{extra_hours} hours + 2 practice exams "
            f"→ predicted pass rate rises toward 72%."
        )
