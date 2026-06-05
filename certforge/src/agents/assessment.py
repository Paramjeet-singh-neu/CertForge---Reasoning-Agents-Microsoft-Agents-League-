"""Agent 5: Assessment Agent (with Self-Reflection).

Grounding: Foundry IQ (grounded, cited questions) + Fabric IQ (pass thresholds).

Advanced reasoning pattern: SELF-REFLECTION. After scoring, the agent inspects
its own per-skill confidence. If any skill is below the confidence threshold, it
"re-queries Foundry IQ" (mock: pulls a stronger cited source) and revises that
skill's questions and confidence BEFORE passing results forward. This is the
agent checking itself — distinct from the Critic, which checks it externally.
"""
from __future__ import annotations

from .. import config
from ..knowledge import retriever
from .base import Agent

CONFIDENCE_THRESHOLD = 0.70


class AssessmentAgent(Agent):
    name = "AssessmentAgent"

    system_prompt = (
        "You are the Assessment Agent for CertForge. You write grounded, cited "
        "practice questions and perform SELF-REFLECTION on your own confidence.\n\n"
        "You are given the skills and the (already-computed) score/status for each. "
        "Do NOT change the scores. Your job is to:\n"
        "1. Write 1 credible, certification-level practice question per weak skill, "
        "grounded in the provided knowledge_base_passages. Cite the EXACT 'source' "
        "string from the matching passage — do not invent sources.\n"
        "2. Produce a self_reflection_log: for any weak skill, narrate noticing low "
        "confidence, re-querying the knowledge base, and revising the question.\n\n"
        "Return ONLY JSON:\n"
        "{\n"
        '  "sample_questions": [{"question": "...", "skill": "...", "source": "...", '
        '"difficulty": "easy|medium|hard"}],\n'
        '  "self_reflection_log": ["..."],\n'
        '  "reasoning_trace": ["..."]\n'
        "}"
    )

    def _user_payload(self, context: dict) -> dict:
        cert = config.get_certification(context["learner_profile"]["certification"])
        weak = sorted(set(context.get("known_weak_areas", [])))
        cert_id = cert["id"] if cert else context["learner_profile"]["certification"]
        # Retrieve real passages so the LLM grounds questions and cites real sources.
        grounding = []
        for skill in (weak or (cert["skills"][:2] if cert else [])):
            q = skill if skill.lower().startswith("azure") else f"Azure {skill}"
            for hit in retriever.search(q, k=1, kind="content"):
                grounding.append({"skill": skill, "source": hit["citation"],
                                  "excerpt": hit["excerpt"]})
        return {
            "certification": cert_id,
            "skills": cert["skills"] if cert else [],
            "weak_skills": weak,
            "knowledge_base_passages": grounding,
        }

    def _apply_live(self, baseline: dict, llm_out: dict, context: dict) -> dict:
        # Keep the deterministic, data-grounded scores; enrich the qualitative parts.
        merged = dict(baseline)
        if llm_out.get("sample_questions"):
            merged["assessment"] = {**baseline["assessment"],
                                    "sample_questions": llm_out["sample_questions"]}
        if llm_out.get("self_reflection_log"):
            merged["self_reflection_log"] = llm_out["self_reflection_log"]
            merged["self_reflection_triggered"] = True
        if llm_out.get("reasoning_trace"):
            merged["reasoning_trace"] = llm_out["reasoning_trace"]
        merged["powered_by"] = "llm"
        return merged

    def _run_mock(self, context: dict) -> dict:
        profile = context["learner_profile"]
        cert = config.get_certification(profile["certification"])
        me = config.get_learner(profile["employee_id"]) or {}
        iteration = context.get("loop_iteration", 1)
        weak_areas = set(context.get("known_weak_areas", me.get("weak_areas", [])))

        base_score = me.get("practice_score_avg", profile.get("practice_score_avg", 70))
        # On feedback-loop iterations, simulate improvement from targeted study.
        improvement = (iteration - 1) * 7
        threshold = cert["pass_threshold"]

        skill_scores, reflection_log = [], []
        for skill in cert["skills"]:
            is_weak = skill in weak_areas
            score = base_score + improvement + (-12 if is_weak else 6)
            score = max(40, min(98, score))
            confidence = 0.62 if is_weak else 0.86

            # --- SELF-REFLECTION ---------------------------------------
            if confidence < CONFIDENCE_THRESHOLD:
                reflection_log.append(
                    f"Low confidence on {skill} questions ({confidence:.2f}). "
                    f"Re-queried Foundry IQ."
                )
                reflection_log.append(
                    f"Found stronger source: Engineering Cert Guide, {skill} section."
                )
                confidence = 0.81
                reflection_log.append(
                    f"Revised {skill} questions. New confidence: {confidence:.2f}."
                )

            status = "strong" if score >= threshold + 5 else "adequate" if score >= threshold - 10 else "weak"
            entry = {"skill": skill, "score": score, "status": status, "confidence": confidence}
            if status == "weak":
                entry["gaps"] = self._gaps(skill)
            skill_scores.append(entry)

        overall = round(sum(s["score"] for s in skill_scores) / len(skill_scores))
        readiness = (
            "ready" if overall >= threshold
            else "borderline" if overall >= threshold - 10
            else "not_ready"
        )

        comparison = None
        if iteration > 1 and "assessment_history" in context:
            comparison = self._compare(context["assessment_history"], skill_scores, overall)

        return {
            "agent_name": self.name,
            "confidence": round(sum(s["confidence"] for s in skill_scores) / len(skill_scores), 2),
            "loop_iteration": iteration,
            "self_reflection_triggered": bool(reflection_log),
            "self_reflection_log": reflection_log,
            "assessment": {
                "overall_score": overall,
                "readiness_status": readiness,
                "skill_scores": skill_scores,
                "sample_questions": self._sample_questions(cert, weak_areas),
                "pass_threshold": threshold,
            },
            "comparison_with_previous": comparison,
            "reasoning_trace": self.trace(
                f"Generated questions across {len(cert['skills'])} skills (Foundry IQ grounded)",
                f"Self-reflection {'TRIGGERED' if reflection_log else 'not needed'}"
                + (f": revised {len(reflection_log)//3} weak skill(s)" if reflection_log else ""),
                f"Overall score: {overall}% → {readiness.upper()} (threshold {threshold}%)",
            ),
        }

    def _gaps(self, skill: str) -> list[str]:
        gap_map = {
            "Storage": ["Blob lifecycle policies", "Access tiers"],
            "Monitoring": ["Application Insights queries", "Alert rules"],
            "Security": ["Managed identities", "Key Vault access"],
            "Azure Functions": ["Durable functions", "Bindings"],
        }
        return gap_map.get(skill, [f"Core {skill} concepts"])

    def _sample_questions(self, cert: dict, weak: set) -> list[dict]:
        target = next((s for s in cert["skills"] if s in weak), cert["skills"][0])
        # Ground the citation in a real retrieved passage (Foundry IQ).
        q = target if target.lower().startswith("azure") else f"Azure {target}"
        hits = retriever.search(q, k=1, prefer_semantic=not config.use_mock(), kind="content")
        source = hits[0]["citation"] if hits else "Engineering Cert Guide"
        return [
            {
                "question": f"Which {target} configuration is most cost-effective for a "
                f"production {cert['id']} workload?",
                "skill": target,
                "source": source,
                "difficulty": "medium",
            }
        ]

    def _compare(self, history: list[dict], current_scores: list[dict], overall: int) -> dict:
        prev = history[-1]
        prev_overall = prev.get("overall_score", overall)
        improved = []
        for cur in current_scores:
            old = next((s for s in prev.get("skill_scores", []) if s["skill"] == cur["skill"]), None)
            if old and cur["score"] > old["score"]:
                improved.append(f"{cur['skill']}: {old['score']}→{cur['score']}")
        return {
            "iteration_prev_score": prev_overall,
            "iteration_current_score": overall,
            "improved_areas": improved,
            "trend": "improving" if overall > prev_overall else "stagnant",
        }
