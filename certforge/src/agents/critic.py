"""Agent 6: Readiness Critic (Devil's Advocate).

Advanced reasoning pattern: CRITIC / VERIFIER with pattern-backed evidence.

The Critic reviews every other agent adversarially and, crucially, backs each
challenge with data from the Pattern Analyst (e.g. "72% looks borderline, but
your matching peers passed only 33% of the time"). Its verdict decides whether
the feedback loop fires:

    READY            -> proceed to Career Pathway
    NEEDS_ADJUSTMENT -> trigger feedback loop (re-plan weak areas)
    CRITICAL_GAPS    -> trigger feedback loop with warnings
"""
from __future__ import annotations

from .base import Agent

HIGH_MEETING_THRESHOLD = 20


class ReadinessCritic(Agent):
    name = "ReadinessCritic"

    def _run_mock(self, context: dict) -> dict:
        assessment = context.get("assessment", {})
        patterns = context.get("patterns", {})
        study_plan = context.get("study_plan", {})
        engagement = context.get("engagement", {})

        a = assessment.get("assessment", {})
        overall = a.get("overall_score", 0)
        readiness = a.get("readiness_status", "not_ready")
        pass_rate = patterns.get("pass_rate", 0.5)
        threshold = a.get("pass_threshold", 75)

        challenges, gaps, approved = [], [], []

        # 1. Challenge the assessment with pattern evidence.
        if readiness != "ready" or pass_rate < 0.6:
            ev = patterns.get("patterns", [{}])
            evidence = ev[0].get("evidence", "pattern data") if ev else "pattern data"
            challenges.append({
                "target_agent": "AssessmentAgent",
                "target_claim": f"{overall}% overall, {readiness}",
                "challenge": f"Pattern data shows {int(pass_rate*100)}% pass rate at this profile",
                "evidence": evidence,
                "severity": "critical" if pass_rate < 0.5 else "significant",
                "revised_recommendation": "Delay exam ~1 week; add hours on weak areas",
            })
        else:
            approved.append("Assessment score is supported by pattern data")

        # 2. Challenge the study plan against work capacity.
        meeting = engagement.get("work_analysis", {}).get("meeting_hours", 0)
        weeks = study_plan.get("plan", {}).get("total_weeks", 0)
        if meeting > HIGH_MEETING_THRESHOLD and weeks < 5:
            challenges.append({
                "target_agent": "StudyPlanGenerator",
                "target_claim": f"{weeks}-week plan with {meeting} meeting hrs/week",
                "challenge": "Historical data shows this workload needs more time",
                "evidence": "Employees with >20 meeting hrs need ~25% more time",
                "severity": "significant",
                "revised_recommendation": "Extend to 5-6 weeks or protect study time",
            })
        else:
            approved.append("Study plan timeline is realistic for the work load")

        # 3. Gaps nobody else caught.
        me_exams = context.get("learner_profile", {}).get("practice_exams_taken")
        success = patterns.get("success_factors", [])
        if any("practice exam" in s for s in success):
            gaps.append(
                "Few practice exams planned — peers with 2+ practice exams pass far more often"
            )

        # Approve well-cited curator content.
        if context.get("curator", {}).get("sources_cited"):
            approved.append("Learning path content is well-cited and appropriate")

        verdict, loop_rec = self._verdict(readiness, pass_rate, challenges)

        return {
            "agent_name": self.name,
            "verdict": verdict,
            "review_summary": self._summary(verdict, overall, pass_rate),
            "challenges": challenges,
            "gaps_identified": gaps,
            "approved_findings": approved,
            "loop_recommendation": loop_rec,
            "reasoning_trace": self.trace(
                f"Cross-checked {overall}% assessment against {int(pass_rate*100)}% peer pass rate",
                f"Raised {len(challenges)} challenge(s), {len(gaps)} gap(s)",
                f"Verdict: {verdict}",
            ),
        }

    def _verdict(self, readiness, pass_rate, challenges):
        critical = any(c["severity"] == "critical" for c in challenges)
        if readiness == "ready" and pass_rate >= 0.6 and not critical:
            return "READY", "PROCEED"
        if critical or pass_rate < 0.4:
            return "CRITICAL_GAPS", "TRIGGER_FEEDBACK_LOOP"
        return "NEEDS_ADJUSTMENT", "TRIGGER_FEEDBACK_LOOP"

    def _summary(self, verdict, overall, pass_rate):
        if verdict == "READY":
            return f"{overall}% with {int(pass_rate*100)}% peer pass rate — cleared with confidence."
        return (
            f"Learner scores {overall}% but matching peers pass only {int(pass_rate*100)}% "
            f"of the time. Recommending more preparation before the exam."
        )
