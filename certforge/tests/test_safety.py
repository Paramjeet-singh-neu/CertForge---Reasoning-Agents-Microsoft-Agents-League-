"""Tests for the Responsible-AI guardrails and the evaluation harness."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation import evaluate  # noqa: E402
from src.memory import procedural_memory as pm  # noqa: E402
from src.pipeline import runner  # noqa: E402
from src.safety import guardrails  # noqa: E402


def setup_function(_):
    pm.reset()
    pm.seed_baseline()


# --- input guardrails --------------------------------------------------------
def test_input_guardrail_blocks_pii():
    ok, issues = guardrails.validate_input("real.person@example.com", "Cloud Engineer", "AZ-204")
    assert not ok
    assert any("PII" in i or "synthetic" in i for i in issues)


def test_input_guardrail_blocks_unknown_cert():
    ok, issues = guardrails.validate_input("EMP-001", "Cloud Engineer", "ZZ-999")
    assert not ok
    assert any("certification" in i for i in issues)


def test_input_guardrail_accepts_valid():
    ok, issues = guardrails.validate_input("EMP-001", "Cloud Engineer", "AZ-204")
    assert ok and not issues


def test_pipeline_blocks_bad_input():
    r = runner.run_analysis("not-synthetic", "Cloud Engineer", "AZ-204")
    assert r.get("blocked") is True
    assert r["guardrail_report"]["passed"] is False


# --- output guardrails -------------------------------------------------------
def test_output_guardrail_passes_on_real_run():
    r = runner.run_analysis("EMP-001", "Cloud Engineer", "AZ-204")
    assert r["guardrail_report"]["passed"] is True
    assert guardrails.validate_output(r) == []


# --- evaluation harness ------------------------------------------------------
def test_evaluation_predictive_accuracy_is_strong():
    results = evaluate.evaluate_all()
    # Leave-one-out accuracy should be clearly better than a coin flip.
    assert results["predictive_accuracy"]["accuracy"] >= 0.8
    assert results["groundedness"]["curator_citation_rate"] == 1.0
    assert results["safety"]["output_guardrail_pass_rate"] == 1.0


def test_adversarial_safety_suite_all_pass():
    suite = guardrails.run_safety_suite()
    # Every adversarial case (PII, injection, out-of-scope, real name) + the
    # valid case must be handled as expected.
    assert suite["passed"] == suite["total"]
    assert suite["pass_rate"] == 1.0


def test_evaluation_reports_fairness():
    results = evaluate.evaluate_all()
    assert "predicted_pass_rate_by_role" in results["fairness"]
    assert results["fairness"]["flag"] in {"ok", "review"}
