"""CertForge Hosted Agent entrypoint (Foundry Agent Service shape).

This is the "entry agent" that Foundry Agent Service hosts. It conforms to the
documented Hosted Agent runtime contract:

  - listens on port 8088
  - exposes the **Responses** protocol:    POST /responses   {"input", "stream"}
  - exposes the **Invocations** protocol:  POST /invocations {arbitrary JSON}
  - exposes a health check:                GET  /healthz

Internally it runs the full CertForge multi-agent pipeline. The Responses
endpoint makes it testable in the Foundry playground / any OpenAI SDK; the
Invocations endpoint matches our structured "analysis in, analysis out" nature.

Local run (matches the quickstart):
    python certforge/agent/main.py
    curl -sS -H "Content-Type: application/json" -X POST http://localhost:8088/responses \
        -d '{"input": "Analyze EMP-001 for AZ-204", "stream": false}'

For managed deployment, the official Foundry protocol library wraps these same
handlers (see DEPLOY.md); the core logic — analyze() — is unchanged.
"""
from __future__ import annotations

import re
import sys
import time
import uuid
from pathlib import Path

# Make `src...` importable (same pattern as the Streamlit app).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src import config  # noqa: E402
from src.memory import procedural_memory  # noqa: E402
from src.pipeline import runner  # noqa: E402

app = FastAPI(title="CertForge Hosted Agent", version="1.0")
procedural_memory.seed_baseline()

_EMP = re.compile(r"\b(EMP-\d+)\b", re.I)
_CERT = re.compile(r"\b(AZ-\d+|DP-\d+)\b", re.I)
_HOURS = re.compile(r"(\d+)\s*(?:hrs|hours)")


# ---------------------------------------------------------------------------
# Core agent logic (protocol-independent, reused by both endpoints)
# ---------------------------------------------------------------------------
def analyze(text_or_params) -> dict:
    """Run the CertForge pipeline from free text or a structured dict."""
    if isinstance(text_or_params, dict):
        emp = text_or_params.get("employee_id", "EMP-001")
        cert = text_or_params.get("certification")
        hours = int(text_or_params.get("available_hours_per_week", 6))
        team = text_or_params.get("team")
    else:
        text = str(text_or_params)
        m_emp, m_cert, m_hours = _EMP.search(text), _CERT.search(text), _HOURS.search(text)
        emp = m_emp.group(1).upper() if m_emp else "EMP-001"
        cert = m_cert.group(1).upper() if m_cert else None
        hours = int(m_hours.group(1)) if m_hours else 6
        team = [e.upper() for e in _EMP.findall(text)] if "team" in text.lower() else None

    if team and len(team) > 1:
        return runner.run_team_analysis(team)

    learner = config.get_learner(emp) or {"role": "Cloud Engineer", "certification": "AZ-204"}
    cert = cert or learner["certification"]
    return runner.run_analysis(emp, learner["role"], cert, hours)


def summarize(result: dict) -> str:
    """One-paragraph natural-language summary for the Responses output_text."""
    if result.get("blocked"):
        return "Request blocked by input guardrail: " + \
            "; ".join(result["guardrail_report"]["violations"])
    if "team_insights" in result:
        ti = result["team_insights"]
        return (f"Team analysis: {ti['team_readiness']}, current pass prediction "
                f"{int(ti['team_pass_prediction']*100)}%. {len(ti['alerts'])} risk alert(s).")
    prof = result["learner_profile"]
    a = result["assessment"]["assessment"]
    verdict = result["critic"]["verdict"]
    return (f"{prof['employee_id']} ({prof['certification']}): {a['overall_score']}% "
            f"after {result['loop_iterations_run']} feedback loop(s) → verdict {verdict}. "
            + (result.get("career_pathway", {}).get("pathway", {}).get("message", "")))


# ---------------------------------------------------------------------------
# Protocol endpoints
# ---------------------------------------------------------------------------
class ResponsesRequest(BaseModel):
    input: str
    stream: bool = False


@app.get("/healthz")
@app.get("/readiness")
@app.get("/liveness")
@app.get("/startup")
def healthz():
    # Foundry Agent Service probes /readiness for session readiness (must be 200).
    return {"status": "ok", "engine": "mock" if config.use_mock() else config.chat_model()}


@app.post("/responses")
def responses(req: ResponsesRequest):
    """Foundry Responses protocol: natural-language in, response object out.

    Returns the standard OpenAI Responses shape (output[] with an assistant
    message) so the Foundry playground and SDK clients render it correctly.
    """
    result = analyze(req.input)
    text = summarize(result)
    rid = f"resp_{uuid.uuid4().hex[:12]}"
    return {
        "id": rid,
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": config.chat_model() if not config.use_mock() else "certforge-mock",
        "output": [
            {
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "output_text": text,
        "metadata": {"certforge": _trim(result)},
    }


@app.post("/invocations")
def invocations(payload: dict):
    """Foundry Invocations protocol: structured JSON in, structured JSON out."""
    result = analyze(payload)
    return _trim(result)


def _trim(result: dict) -> dict:
    """Return the demo-relevant slice of the result (keeps payloads small)."""
    if "team_insights" in result:
        return {"team_insights": result["team_insights"]}
    if result.get("blocked"):
        return result
    return {
        "learner_profile": result.get("learner_profile"),
        "assessment": result.get("assessment", {}).get("assessment"),
        "critic_verdict": result.get("critic", {}).get("verdict"),
        "predictor": result.get("predictor", {}).get("scenarios"),
        "career_pathway": result.get("career_pathway", {}).get("pathway"),
        "loop_iterations": result.get("loop_iterations_run"),
        "guardrail_report": result.get("guardrail_report"),
        "telemetry": result.get("telemetry"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8088)
