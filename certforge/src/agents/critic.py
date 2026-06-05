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


VALID_VERDICTS = {"READY", "NEEDS_ADJUSTMENT", "CRITICAL_GAPS"}


class ReadinessCritic(Agent):
    name = "ReadinessCritic"

    system_prompt = (
        "You are the Readiness Critic for CertForge, the hardest reviewer in an "
        "enterprise certification system. You review other agents' findings "
        "ADVERSARIALLY and back every challenge with the pattern evidence given. "
        "Do not be agreeable — your job is to catch over-optimism.\n\n"
        "VERDICT RUBRIC (apply strictly):\n"
        "- READY: overall_score >= pass_threshold AND pass_rate_for_profile >= 0.70.\n"
        "- CRITICAL_GAPS: pass_rate_for_profile < 0.45, or score far below threshold.\n"
        "- NEEDS_ADJUSTMENT: anything in between.\n"
        "The pass_rate_for_profile ALREADY reflects any extra study applied this "
        "iteration — trust it as the learner's current projected odds.\n\n"
        "Rules:\n"
        "- Even when you return READY, you may note residual caveats in challenges.\n"
        "- Challenge the study plan only if the timeline is unrealistic for the work load.\n"
        "- Cite the provided evidence verbatim in each challenge.\n\n"
        "Return ONLY JSON with this exact shape:\n"
        "{\n"
        '  "verdict": "READY" | "NEEDS_ADJUSTMENT" | "CRITICAL_GAPS",\n'
        '  "review_summary": "<2 sentences>",\n'
        '  "challenges": [{"target_agent": "...", "target_claim": "...", '
        '"challenge": "...", "evidence": "...", "severity": "critical|significant|minor", '
        '"revised_recommendation": "..."}],\n'
        '  "gaps_identified": ["..."],\n'
        '  "approved_findings": ["..."],\n'
        '  "reasoning_trace": ["step 1", "step 2"]\n'
        "}"
    )

    def _user_payload(self, context: dict) -> dict:
        a = context.get("assessment", {}).get("assessment", {})
        patterns = context.get("patterns", {})
        plan = context.get("study_plan", {}).get("plan", {})
        work = context.get("engagement", {}).get("work_analysis", {})
        return {
            "loop_iteration": context.get("loop_iteration", 1),
            "assessment": {
                "overall_score": a.get("overall_score"),
                "readiness_status": a.get("readiness_status"),
                "pass_threshold": a.get("pass_threshold"),
                "weak_skills": [s["skill"] for s in a.get("skill_scores", [])
                                if s.get("status") == "weak"],
            },
            "pattern_evidence": {
                "pass_rate_for_profile": patterns.get("pass_rate"),
                "patterns": patterns.get("patterns", []),
                "success_factors": patterns.get("success_factors", []),
                "failure_factors": patterns.get("failure_factors", []),
            },
            "study_plan": {"total_weeks": plan.get("total_weeks"),
                           "total_hours": plan.get("total_hours")},
            "work_context": {"meeting_hours": work.get("meeting_hours"),
                             "capacity_risk": work.get("capacity_risk")},
        }

    def _apply_live(self, baseline: dict, llm_out: dict, context: dict) -> dict:
        verdict = str(llm_out.get("verdict", "")).upper().strip()
        if verdict not in VALID_VERDICTS:
            # LLM produced an invalid verdict -> trust the deterministic one.
            return baseline

        # GUARDRAIL: keep the LLM's rich critique, but enforce hard verdict bounds
        # so the feedback loop reliably converges and over/under-confidence can't
        # slip through. (Responsible-AI style bound on an LLM decision.)
        a = context.get("assessment", {}).get("assessment", {})
        score = a.get("overall_score", 0)
        threshold = a.get("pass_threshold", 75)
        pass_rate = context.get("patterns", {}).get("pass_rate", 0.5)
        if score >= threshold and pass_rate >= 0.70:
            verdict = "READY"
        elif pass_rate < 0.45:
            verdict = "CRITICAL_GAPS"

        loop_rec = "PROCEED" if verdict == "READY" else "TRIGGER_FEEDBACK_LOOP"
        merged = dict(baseline)
        merged.update({
            "verdict": verdict,
            "review_summary": llm_out.get("review_summary", baseline["review_summary"]),
            "challenges": llm_out.get("challenges", baseline["challenges"]),
            "gaps_identified": llm_out.get("gaps_identified", baseline["gaps_identified"]),
            "approved_findings": llm_out.get("approved_findings", baseline["approved_findings"]),
            "reasoning_trace": llm_out.get("reasoning_trace", baseline["reasoning_trace"]),
            "loop_recommendation": loop_rec,
            "powered_by": "llm",
        })
        return merged

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
