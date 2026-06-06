"""Smoke / regression tests for the CertForge mock pipeline.

These pin the demo-critical behaviours so future changes (especially the Azure
swap) can't silently break the narrative:
  - the full pipeline runs and emits every expected agent
  - an at-risk learner improves across the feedback loop and reaches READY
  - a strong learner passes on the first iteration
  - the team heatmap distinguishes risk levels
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.memory import procedural_memory as pm  # noqa: E402
from src.pipeline import runner  # noqa: E402


def setup_function(_):
    pm.reset()
    pm.seed_baseline()


def test_full_pipeline_emits_all_agents():
    r = runner.run_analysis("EMP-001", "Cloud Engineer", "AZ-204", 6)
    agents = {e["agent"] for e in r["event_log"]}
    for expected in {"Orchestrator", "LearningPathCurator", "StudyPlanGenerator",
                     "EngagementAgent", "PerformancePatternAnalyst", "AssessmentAgent",
                     "ReadinessCritic", "OutcomePredictor", "ManagerInsightsAgent"}:
        assert expected in agents, f"missing {expected}"


def test_at_risk_learner_improves_through_loop():
    r = runner.run_analysis("EMP-001", "Cloud Engineer", "AZ-204", 6)
    assert r["initial_status"] in {"borderline", "not_ready"}
    assert r["loop_iterations_run"] >= 2
    assert r["critic"]["verdict"] == "READY"
    assert "career_pathway" in r  # ready -> pathway fires


def test_strong_learner_passes_first_try():
    r = runner.run_analysis("EMP-009", "Cloud Engineer", "AZ-204", 6)
    assert r["loop_iterations_run"] == 1
    assert r["critic"]["verdict"] == "READY"


def test_team_heatmap_has_mixed_risk():
    out = runner.run_team_analysis(["EMP-001", "EMP-004", "EMP-009", "EMP-012"])
    risks = {row["risk"] for row in out["team_insights"]["risk_heatmap"]}
    assert "high" in risks and "low" in risks


def test_human_in_the_loop_gate():
    # Prep stage stops at the human gate — no assessment yet.
    prep = runner.run_prep("EMP-001", "Cloud Engineer", "AZ-204", 6)
    assert prep["human_gate"]["stage"] == "awaiting_confirmation"
    assert "assessment" not in prep
    assert "curator" in prep and "study_plan" in prep  # prep agents ran
    # After human confirmation, assessment proceeds.
    full = runner.run_assessment(prep)
    assert full["human_gate"]["stage"] == "confirmed"
    assert full["critic"]["verdict"] in {"READY", "NEEDS_ADJUSTMENT", "CRITICAL_GAPS"}


def test_procedural_memory_learns():
    runner.run_analysis("EMP-001", "Cloud Engineer", "AZ-204", 6)
    assert len(pm.all_patterns()) >= 5
