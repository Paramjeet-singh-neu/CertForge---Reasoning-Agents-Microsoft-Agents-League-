"""Pipeline runner — the execution half of the planner-executor pattern.

run_analysis() drives one learner through the whole system:

  Orchestrator (plan)
    → [Curator, StudyPlan, Engagement, PatternAnalyst] in parallel
    → Assessment (self-reflection)
    → Critic
    → Predictor
    → if Critic says NOT READY and loops remain: re-plan weak areas, repeat
    → if READY: Career Pathway
    → Manager Insights (individual)
    → learn patterns into procedural memory

Every agent's output is collected into one `result` dict, and a flat
`event_log` records the order of execution for the Reasoning Trace viewer.

In mock mode the four "parallel" agents run sequentially (they're instant); the
structure is what matters and it maps cleanly onto real async/parallel calls.
"""
from __future__ import annotations

from ..agents.assessment import AssessmentAgent
from ..agents.career_pathway import CareerPathwayAgent
from ..agents.critic import ReadinessCritic
from ..agents.curator import LearningPathCurator
from ..agents.engagement import EngagementAgent
from ..agents.manager_insights import ManagerInsightsAgent
from ..agents.orchestrator import MAX_LOOPS, Orchestrator
from ..agents.pattern_analyst import PerformancePatternAnalyst
from ..agents.predictor import OutcomePredictor
from ..agents.study_plan import StudyPlanGenerator
from ..memory import procedural_memory
from ..safety import guardrails

PARALLEL_AGENTS = [
    ("curator", LearningPathCurator),
    ("study_plan", StudyPlanGenerator),
    ("engagement", EngagementAgent),
    ("patterns", PerformancePatternAnalyst),
]


def _recorder(event_log: list[dict]):
    def record(out: dict):
        event_log.append({
            "agent": out.get("agent_name"),
            "elapsed_seconds": out.get("elapsed_seconds"),
            "trace": out.get("reasoning_trace", []),
        })
    return record


def run_prep(employee_id: str, role: str, certification: str,
             available_hours_per_week: int = 6, topics: str = "") -> dict:
    """Prep stage: Orchestrator + Curator/Study Plan/Engagement/Patterns, then
    STOP at the human-in-the-loop gate ("Ready to be assessed?").

    Returns a context with `human_gate` awaiting confirmation. Call run_assessment
    to continue once the human confirms.
    """
    ok, issues = guardrails.validate_input(employee_id, role, certification)
    if not ok:
        return {
            "blocked": True,
            "guardrail_report": {"passed": False, "violations": issues,
                                 "transparency_notice": guardrails.TRANSPARENCY_NOTICE},
            "learner_profile": {"employee_id": employee_id, "role": role,
                                "certification": certification},
            "event_log": [{"agent": "InputGuardrail", "trace": issues}],
        }

    context: dict = {
        "learner_profile": {
            "employee_id": employee_id,
            "role": role,
            "certification": certification,
            "available_hours_per_week": available_hours_per_week,
        },
        "learner_topics": topics.strip(),
        "loop_iteration": 1,
        "event_log": [],
    }
    record = _recorder(context["event_log"])

    # --- Orchestrator: plan ------------------------------------------------
    plan = Orchestrator().run(context)
    record(plan)
    context["learner_profile"] = plan["learner_profile"]
    context["known_weak_areas"] = plan["learner_profile"].get("weak_areas", [])
    context["memory_patterns_applied"] = plan["memory_patterns_applied"]

    # --- Parallel analysis agents -----------------------------------------
    for key, AgentCls in PARALLEL_AGENTS:
        out = AgentCls().run(context)
        context[key] = out
        record(out)

    # --- HUMAN-IN-THE-LOOP GATE -------------------------------------------
    # Prep is done. A human (learner/manager) reviews the plan and decides
    # whether the learner is ready to be assessed before assessment runs.
    context["human_gate"] = {
        "stage": "awaiting_confirmation",
        "question": "Ready to be assessed?",
        "summary": (f"Study plan ready: {context['study_plan']['plan']['total_weeks']} weeks, "
                    f"{context['study_plan']['plan']['total_hours']} hrs. "
                    f"Capacity risk: {context['engagement']['work_analysis']['capacity_risk']}."),
    }
    context["event_log"].append({"agent": "HumanInTheLoop", "trace": [
        "Prep complete — awaiting human confirmation: 'Ready to be assessed?'"]})
    return context


def run_assessment(context: dict) -> dict:
    """Assessment stage (post human gate): reasoning agents + feedback loop +
    branch + manager synthesis + memory. Mutates and returns the context."""
    context.setdefault("event_log", [])
    record = _recorder(context["event_log"])
    certification = context["learner_profile"]["certification"]
    if context.get("human_gate"):
        context["human_gate"]["stage"] = "confirmed"
        context["event_log"].append({"agent": "HumanInTheLoop", "trace": [
            "Human confirmed readiness — proceeding to assessment."]})

    # --- Sequential reasoning + feedback loop ------------------------------
    assessment_history: list[dict] = []
    final_verdict = None
    # The base (historical) pass rate never changes, but each revision adds study
    # hours + a practice exam, which should raise the learner's *predicted* odds.
    base_pass_rate = context["patterns"]["pass_rate"]
    coeffs = context["patterns"].get("what_if_coefficients", {})
    cumulative_hours = 0
    cumulative_exams = 0
    for iteration in range(1, MAX_LOOPS + 1):
        context["loop_iteration"] = iteration
        if assessment_history:
            context["assessment_history"] = assessment_history

        if iteration > 1:
            # Re-plan: narrow the study plan to weak areas, then re-assess.
            context["study_plan"] = StudyPlanGenerator().run(context)
            record(context["study_plan"])
            # Account for the revision's added effort in the predicted pass rate.
            revision = context["study_plan"]["plan"].get("revision_focus") or {}
            cumulative_hours += revision.get("additional_hours", 6)
            cumulative_exams += 1
            new_rate = OutcomePredictor.recompute(
                base_pass_rate, coeffs,
                add_hours=cumulative_hours, add_exams=cumulative_exams)
            # Update BOTH the number and the evidence text so the deterministic
            # and LLM critics see a consistent story (no stale "33%" lingering).
            context["patterns"] = {
                **context["patterns"],
                "pass_rate": new_rate,
                "patterns": [{
                    "pattern": f"Projected pass rate after added study: {int(new_rate*100)}%",
                    "evidence": f"+{cumulative_hours} hrs and +{cumulative_exams} practice "
                                f"exam(s) applied to base {int(base_pass_rate*100)}%",
                    "confidence": 0.75,
                }],
            }
            context["event_log"].append({"agent": "FeedbackLoop", "trace": [
                f"Iteration {iteration}: revised plan (+{cumulative_hours} hrs, "
                f"+{cumulative_exams} practice exam(s)) → "
                f"predicted pass rate now {int(context['patterns']['pass_rate']*100)}%"]})

        context["assessment"] = AssessmentAgent().run(context)
        record(context["assessment"])
        assessment_history.append(context["assessment"]["assessment"])

        context["critic"] = ReadinessCritic().run(context)
        record(context["critic"])

        context["predictor"] = OutcomePredictor().run(context)
        record(context["predictor"])

        # Snapshot the learner's real, pre-intervention state on the first pass.
        # The manager risk heatmap uses this, not the post-loop "ready".
        if iteration == 1:
            context["initial_verdict"] = context["critic"]["verdict"]
            context["initial_score"] = context["assessment"]["assessment"]["overall_score"]
            context["initial_status"] = context["assessment"]["assessment"]["readiness_status"]
            context["initial_pass_rate"] = base_pass_rate

        final_verdict = context["critic"]["verdict"]
        if final_verdict == "READY" or context["critic"]["loop_recommendation"] == "PROCEED":
            break

    context["loop_iterations_run"] = context["loop_iteration"]

    # --- Branch: ready → career pathway -----------------------------------
    if final_verdict == "READY":
        context["career_pathway"] = CareerPathwayAgent().run(context)
        record(context["career_pathway"])

    # --- Synthesize individual report --------------------------------------
    context["manager_individual"] = ManagerInsightsAgent().run(
        {"mode": "individual", "result": context})
    record(context["manager_individual"])

    # --- Learn into procedural memory --------------------------------------
    context["patterns_learned"] = procedural_memory.learn_from_result(certification, context)

    # OUTPUT GUARDRAIL: attach a well-formedness + safety report.
    guardrails.assert_safe_output(context)
    # TELEMETRY: record an observability summary + append to the trace log.
    from .. import telemetry
    context["telemetry"] = telemetry.record(context)
    return context


def run_analysis(employee_id: str, role: str, certification: str,
                 available_hours_per_week: int = 6, topics: str = "") -> dict:
    """Full analysis = prep + assessment (auto-confirms the human gate).

    Used by team batch mode, the hosted agent endpoint, and tests. The UI uses
    run_prep / run_assessment separately to surface the human-in-the-loop gate.
    """
    prep = run_prep(employee_id, role, certification, available_hours_per_week, topics)
    if prep.get("blocked"):
        return prep
    return run_assessment(prep)


def run_team_analysis(employee_ids: list[str]) -> dict:
    """Batch-process a team and synthesize the manager dashboard."""
    from .. import config
    results = []
    for emp in employee_ids:
        learner = config.get_learner(emp)
        if not learner:
            continue
        results.append(run_analysis(emp, learner["role"], learner["certification"]))

    team = ManagerInsightsAgent().run({"mode": "team", "results": results})
    return {"team_insights": team, "learner_results": results}
