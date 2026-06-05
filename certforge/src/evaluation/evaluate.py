"""Evaluation harness for CertForge.

The challenge rewards "evaluation strategies using test cases, scoring rubrics,
or human review." We have something stronger than a rubric: **ground truth**.
Every synthetic learner has a real `exam_outcome`, and the Pattern Analyst
derives a learner's pass probability from their *cohort excluding themselves*
(leave-one-out), so validating predictions against actual outcomes is fair.

Four evaluation dimensions:
  1. PREDICTIVE ACCURACY — does our pre-intervention risk predict pass/fail?
  2. GROUNDEDNESS        — do outputs carry citations / sources?
  3. SAFETY/VALIDITY     — do all outputs pass the output guardrail?
  4. FAIRNESS            — is predicted readiness balanced across roles?

Runs in mock (deterministic) mode so results are fast and reproducible.
"""
from __future__ import annotations

from statistics import mean

from .. import config
from ..memory import procedural_memory
from ..pipeline import runner
from ..safety import guardrails

PASS_PROB_THRESHOLD = 0.5  # predicted "likely pass" if base pass probability >= this


def evaluate_all() -> dict:
    """Run the pipeline over every learner and compute evaluation metrics."""
    procedural_memory.reset()
    procedural_memory.seed_baseline()

    rows = []
    for learner in config.learners():
        result = runner.run_analysis(
            learner["employee_id"], learner["role"], learner["certification"])
        rows.append(_score_one(learner, result))

    return {
        "n": len(rows),
        "predictive_accuracy": _accuracy(rows),
        "groundedness": _groundedness(rows),
        "safety": _safety(rows),
        "fairness": _fairness(rows),
        "per_learner": rows,
    }


def _score_one(learner: dict, result: dict) -> dict:
    actual_pass = learner["exam_outcome"].lower() == "pass"
    base_prob = result.get("initial_pass_rate",
                           result.get("patterns", {}).get("pass_rate", 0.5))
    predicted_pass = base_prob >= PASS_PROB_THRESHOLD

    a = result.get("assessment", {}).get("assessment", {})
    cited_qs = sum(1 for q in a.get("sample_questions", []) if q.get("source"))
    total_qs = len(a.get("sample_questions", [])) or 1
    curator_cited = bool(result.get("curator", {}).get("sources_cited"))

    return {
        "employee_id": learner["employee_id"],
        "role": learner["role"],
        "certification": learner["certification"],
        "actual_pass": actual_pass,
        "predicted_pass": predicted_pass,
        "base_pass_prob": round(base_prob, 2),
        "correct": predicted_pass == actual_pass,
        "questions_cited_ratio": cited_qs / total_qs,
        "curator_cited": curator_cited,
        "guardrail_violations": guardrails.validate_output(result),
    }


def _accuracy(rows: list[dict]) -> dict:
    n = len(rows)
    correct = sum(r["correct"] for r in rows)
    tp = sum(1 for r in rows if r["predicted_pass"] and r["actual_pass"])
    fp = sum(1 for r in rows if r["predicted_pass"] and not r["actual_pass"])
    fn = sum(1 for r in rows if not r["predicted_pass"] and r["actual_pass"])
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "accuracy": round(correct / n, 2),
        "precision": round(precision, 2),
        "recall": round(recall, 2),
        "f1": round(f1, 2),
        "correct": correct,
        "total": n,
        "method": "leave-one-out vs actual exam_outcome",
    }


def _groundedness(rows: list[dict]) -> dict:
    return {
        "avg_question_citation_ratio": round(mean(r["questions_cited_ratio"] for r in rows), 2),
        "curator_citation_rate": round(mean(1.0 if r["curator_cited"] else 0.0 for r in rows), 2),
    }


def _safety(rows: list[dict]) -> dict:
    clean = sum(1 for r in rows if not r["guardrail_violations"])
    return {
        "output_guardrail_pass_rate": round(clean / len(rows), 2),
        "learners_with_violations": [r["employee_id"] for r in rows if r["guardrail_violations"]],
    }


def _fairness(rows: list[dict]) -> dict:
    """Predicted-pass rate per role + the disparity between best and worst role.

    A large gap would flag the system favouring some roles — a bias signal to
    surface, not hide.
    """
    by_role: dict[str, list[bool]] = {}
    for r in rows:
        by_role.setdefault(r["role"], []).append(r["predicted_pass"])
    rates = {role: round(mean(1.0 if p else 0.0 for p in preds), 2)
             for role, preds in by_role.items()}
    disparity = round(max(rates.values()) - min(rates.values()), 2) if rates else 0.0
    return {
        "predicted_pass_rate_by_role": rates,
        "max_disparity": disparity,
        "flag": "review" if disparity > 0.5 else "ok",
    }


def format_report(results: dict) -> str:
    """Human-readable summary for the CLI / README."""
    acc, g, s, f = (results["predictive_accuracy"], results["groundedness"],
                    results["safety"], results["fairness"])
    lines = [
        "═══ CertForge Evaluation Report ═══",
        f"Learners evaluated: {results['n']}",
        "",
        "1. PREDICTIVE ACCURACY (leave-one-out vs actual outcomes)",
        f"   accuracy={acc['accuracy']}  precision={acc['precision']}  "
        f"recall={acc['recall']}  f1={acc['f1']}  ({acc['correct']}/{acc['total']})",
        "",
        "2. GROUNDEDNESS",
        f"   question citation ratio={g['avg_question_citation_ratio']}  "
        f"curator citation rate={g['curator_citation_rate']}",
        "",
        "3. SAFETY / OUTPUT VALIDITY",
        f"   output guardrail pass rate={s['output_guardrail_pass_rate']}",
        "",
        "4. FAIRNESS (predicted pass rate by role)",
        f"   {f['predicted_pass_rate_by_role']}  max_disparity={f['max_disparity']}  "
        f"[{f['flag']}]",
    ]
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    print(format_report(evaluate_all()))
