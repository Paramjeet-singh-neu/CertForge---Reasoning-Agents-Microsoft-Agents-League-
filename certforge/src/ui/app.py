"""CertForge Streamlit dashboard.

Three views (Learner / Manager / Reasoning Trace) over the same multi-agent
pipeline. The app never contains business logic — it only renders the `result`
dicts the agents produce. The What-If sliders call the *same* OutcomePredictor
math the agent used, so the live numbers and the agent's numbers always agree.

Run:  streamlit run certforge/src/ui/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `src...` importable when Streamlit runs this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src import config  # noqa: E402
from src.agents.predictor import OutcomePredictor  # noqa: E402
from src.memory import procedural_memory  # noqa: E402
from src.pipeline import runner  # noqa: E402

st.set_page_config(page_title="CertForge", page_icon="🎓", layout="wide")

# Seed procedural memory once per session so the first run shows memory in use.
if "memory_seeded" not in st.session_state:
    procedural_memory.seed_baseline()
    st.session_state.memory_seeded = True

RISK_EMOJI = {"low": "🟢", "medium": "🟡", "high": "🔴"}
STATUS_EMOJI = {"ready": "✅", "borderline": "⚠️", "not_ready": "🔴"}


# ---------------------------------------------------------------------------
# Shared rendering helpers
# ---------------------------------------------------------------------------
def score_bar(label: str, score: int, status: str):
    emoji = {"strong": "✅", "adequate": "⚠️", "weak": "🔴"}.get(status, "")
    st.markdown(f"**{label}** {emoji}")
    st.progress(min(score, 100) / 100, text=f"{score}%")


def prob_bars(scenarios: dict):
    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Pass", f"{int(scenarios['pass']['probability']*100)}%")
    c2.metric("🟡 Borderline", f"{int(scenarios['borderline']['probability']*100)}%")
    c3.metric("🔴 Fail", f"{int(scenarios['fail']['probability']*100)}%")


def agent_activity(event_log: list[dict]):
    for e in event_log:
        icon = "🔄" if e["agent"] == "FeedbackLoop" else "🧠"
        line = f"{icon} **{e['agent']}**"
        if e.get("trace"):
            line += " — " + e["trace"][0]
        st.markdown(line)


# ---------------------------------------------------------------------------
# Learner view
# ---------------------------------------------------------------------------
def learner_view():
    st.subheader("👤 Learner View")
    learners = config.learners()
    ids = [l["employee_id"] for l in learners]

    col1, col2, col3 = st.columns([2, 2, 1])
    emp = col1.selectbox("Learner", ids, index=0)
    learner = config.get_learner(emp)
    cert = col2.selectbox(
        "Target certification",
        [c["id"] for c in config.semantic_model()["certifications"]],
        index=[c["id"] for c in config.semantic_model()["certifications"]].index(
            learner["certification"]),
    )
    hours = col3.number_input("Hrs/week", min_value=2, max_value=20, value=6)
    st.caption(f"Role: **{learner['role']}**  ·  Team signal loaded from Work IQ")

    if st.button("🚀 Analyse Readiness", type="primary"):
        with st.spinner("Agents reasoning..."):
            st.session_state.result = runner.run_analysis(
                emp, learner["role"], cert, hours)

    result = st.session_state.get("result")
    if not result or result["learner_profile"]["employee_id"] != emp:
        st.info("Select a learner and click **Analyse Readiness**.")
        return

    # --- Agent activity ---------------------------------------------------
    with st.expander("🧠 Agent Activity", expanded=True):
        if result.get("memory_patterns_applied"):
            st.caption("Memory patterns applied: " +
                       "; ".join(result["memory_patterns_applied"]))
        agent_activity(result["event_log"])

    st.divider()

    # --- Readiness report -------------------------------------------------
    a = result["assessment"]["assessment"]
    verdict = result["critic"]["verdict"]
    loops = result["loop_iterations_run"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall score", f"{a['overall_score']}%")
    c2.metric("Critic verdict", verdict)
    c3.metric("Feedback loops", loops)
    if loops > 1:
        st.success(f"Improved from {result['initial_score']}% to "
                   f"{a['overall_score']}% across {loops} feedback iterations.")

    st.markdown("#### Skill Scores")
    for s in a["skill_scores"]:
        score_bar(s["skill"], s["score"], s["status"])

    # --- Gamification -----------------------------------------------------
    g = result["manager_individual"]["gamification"]
    st.markdown("#### 🏆 Gamification")
    gc1, gc2 = st.columns(2)
    gc1.metric("🔥 Study streak", f"{g['study_streak_days']} days")
    gc2.metric("📊 Percentile", f"{g['percentile']}th")
    st.write("  ·  ".join(f"{k} {v}" for k, v in g["skill_badges"].items()))

    st.divider()

    # --- Outcome prediction + What-If simulator ---------------------------
    pred = result["predictor"]
    st.markdown("#### 🔮 Outcome Prediction")
    prob_bars(pred["scenarios"])

    st.markdown("#### ⚡ What-If Simulator")
    st.caption("Adjust the levers — pass probability recomputes live "
               "(same model the predictor used).")
    base = result.get("initial_pass_rate", pred["base_pass_probability"])
    coeffs = pred["what_if_coefficients"]
    s1, s2, s3 = st.columns(3)
    add_hours = s1.slider("Additional study hours", 0, 12, 0)
    add_exams = s2.slider("Additional practice exams", 0, 4, 0)
    morning = s3.toggle("Switch to morning study")
    new_p = OutcomePredictor.recompute(
        base, coeffs, add_hours=add_hours, add_exams=add_exams, morning=morning)
    st.progress(new_p, text=f"Predicted pass rate: {int(new_p*100)}% "
                            f"(base {int(base*100)}%)")
    if new_p > base:
        st.caption(f"▲ +{int((new_p-base)*100)} points from your adjustments.")

    # --- Career pathway ---------------------------------------------------
    if "career_pathway" in result:
        st.divider()
        st.markdown("#### 🗺️ Career Pathway")
        st.success(result["career_pathway"]["pathway"]["message"])


# ---------------------------------------------------------------------------
# Manager view
# ---------------------------------------------------------------------------
def manager_view():
    st.subheader("📊 Team Certification Dashboard")
    ids = [l["employee_id"] for l in config.learners()]
    default_team = [w["employee_id"] for w in config.work_signals()
                    if w["team"] == "TEAM-A"]
    team = st.multiselect("Team members", ids, default=default_team)

    if st.button("👥 Run Team Analysis", type="primary"):
        with st.spinner(f"Analysing {len(team)} learners..."):
            st.session_state.team = runner.run_team_analysis(team)

    out = st.session_state.get("team")
    if not out:
        st.info("Pick team members and click **Run Team Analysis**.")
        return

    ti = out["team_insights"]
    c1, c2 = st.columns(2)
    c1.metric("Team readiness (now)", ti["team_readiness"])
    c2.metric("Current pass prediction", f"{int(ti['team_pass_prediction']*100)}%")

    st.markdown("#### Risk Heatmap")
    df = pd.DataFrame([
        {
            "Learner": r["employee_id"],
            "Cert": r["certification"],
            "Score now": f"{r['score']}%",
            "Status": f"{STATUS_EMOJI.get(r['status'],'')} {r['status']}",
            "Risk": f"{RISK_EMOJI[r['risk']]} {r['risk'].upper()}",
            "Loops→Ready": r["loops_to_ready"],
        }
        for r in ti["risk_heatmap"]
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    if ti["alerts"]:
        st.markdown("#### 🚨 Risk Alerts")
        for al in ti["alerts"]:
            st.warning(al)

    st.markdown("#### 💡 Pattern Insights (Procedural Memory)")
    for p in ti["pattern_insights"]:
        st.markdown(f"- {p}")

    st.markdown("#### 📋 Recommended Actions")
    for act in ti["recommended_actions"]:
        st.markdown(f"- {act}")

    st.info("🧠 " + ti["memory_insight"])


# ---------------------------------------------------------------------------
# Reasoning trace view
# ---------------------------------------------------------------------------
def trace_view():
    st.subheader("🔍 Reasoning Trace")
    result = st.session_state.get("result")
    if not result:
        st.info("Run a learner analysis first (Learner View), then inspect its trace here.")
        return
    st.caption(f"Trace for {result['learner_profile']['employee_id']} — "
               f"{len(result['event_log'])} agent events")
    for e in result["event_log"]:
        secs = e.get("elapsed_seconds")
        title = f"▸ {e['agent']}" + (f"  ({secs}s)" if secs else "")
        with st.expander(title):
            for step in e.get("trace", []):
                st.markdown(f"- {step}")


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
st.title("🎓 CertForge — Certification Intelligence")
st.caption("8-agent reasoning system · Microsoft IQ-grounded · "
           "synthetic data only, for demonstration")
mode = "🟢 MOCK mode (local)" if config.use_mock() else "☁️ Azure mode"
st.sidebar.markdown(f"**Engine:** {mode}")
st.sidebar.markdown("---")
view = st.sidebar.radio("View", ["👤 Learner", "📊 Manager", "🔍 Reasoning Trace"])

if view.startswith("👤"):
    learner_view()
elif view.startswith("📊"):
    manager_view()
else:
    trace_view()
