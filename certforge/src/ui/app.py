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

from src import config, fabric_iq, telemetry  # noqa: E402
from src.agents.predictor import OutcomePredictor  # noqa: E402
from src.evaluation import evaluate  # noqa: E402
from src.memory import procedural_memory  # noqa: E402
from src.pipeline import runner  # noqa: E402
from src.safety import guardrails  # noqa: E402

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
    topics = st.text_input(
        "Topics you want to focus on (optional)",
        placeholder="e.g. Storage, Monitoring, Azure Functions",
        help="Free-text topics — the Learning Path Curator prioritises matching skills.")
    st.caption(f"Role: **{learner['role']}**  ·  Team signal loaded from Work IQ")

    # --- Step 1: PREP (Curator / Study Plan / Engagement) ----------------
    if st.button("📋 Build Study Plan & Engagement", type="primary"):
        with st.spinner("Curating path, planning, reading Work IQ..."):
            st.session_state.prep = runner.run_prep(
                emp, learner["role"], cert, hours, topics=topics)
            st.session_state.result = None  # reset any prior assessment

    prep = st.session_state.get("prep")
    if not prep or prep["learner_profile"]["employee_id"] != emp:
        st.info("Pick a learner and click **Build Study Plan & Engagement**.")
        return
    if prep.get("blocked"):
        st.error("Request blocked by guardrail: " +
                 "; ".join(prep["guardrail_report"]["violations"]))
        return

    result = st.session_state.get("result")

    # --- Agent activity (live) -------------------------------------------
    with st.expander("🧠 Agent Activity", expanded=True):
        if prep.get("memory_patterns_applied"):
            st.caption("Memory patterns applied: " + "; ".join(prep["memory_patterns_applied"]))
        agent_activity((result or prep)["event_log"])

    # --- Learning path (Curator: Foundry IQ + MS Learn MCP) --------------
    cur = prep.get("curator", {})
    with st.expander("📚 Learning Path (Foundry IQ + MS Learn MCP)", expanded=False):
        matched = cur.get("topics_matched_to_skills")
        if matched:
            st.caption(f"🎯 Prioritised your requested topics: {', '.join(matched)}")
        for s in cur.get("required_skills", []):
            mods = " · ".join(f"[{m['source']}] {m['title']}" for m in s.get("modules", []))
            st.markdown(f"- **{s['skill']}** ({s['priority']}) — {mods}")

    # --- Study plan ------------------------------------------------------
    plan = prep.get("study_plan", {}).get("plan", {})
    st.markdown(f"#### 📅 Study Plan — {plan.get('total_weeks','?')} weeks · "
                f"{plan.get('total_hours','?')} hrs · target {plan.get('target_exam_date','?')}")

    # --- Work IQ -> Engagement & reminders -------------------------------
    eng = prep.get("engagement", {})
    reminders = eng.get("reminder_schedule", [])
    if reminders:
        with st.expander("🗓️ Work IQ → Engagement (Study Windows & Reminders)", expanded=False):
            wa = eng.get("work_analysis", {})
            st.markdown("**Work IQ signals**")
            st.caption(f"{wa.get('meeting_hours','?')} mtg hrs / {wa.get('focus_hours','?')} "
                       f"focus hrs · preferred {wa.get('preferred_slot','?')} · "
                       f"collaboration **{wa.get('collaboration_load','?')}** · "
                       f"availability **{wa.get('availability','?')}**")
            if wa.get("flow_of_work_note"):
                st.caption(f"🧭 {wa['flow_of_work_note']}")
            st.caption(f"_source: {wa.get('work_iq_source','synthetic')}_")
            rs = eng.get("reminder_strategy", {})
            st.caption(f"Cadence: **{rs.get('frequency')}** · tone {rs.get('tone')} · "
                       f"{rs.get('escalation')}")
            st.dataframe(pd.DataFrame([
                {"Day": r["day"], "Time": r["time"], "Channel": r.get("channel", ""),
                 "Reminder": r["message"]} for r in reminders
            ]), use_container_width=True, hide_index=True)

    # --- HUMAN-IN-THE-LOOP gate ------------------------------------------
    if not result:
        st.divider()
        gate = prep.get("human_gate", {})
        st.warning(f"🧑‍⚖️ **Human-in-the-loop — {gate.get('question','Ready to be assessed?')}**\n\n"
                   f"{gate.get('summary','')}")
        if not st.button("✅ Confirm ready → Run Assessment", type="primary"):
            st.caption("Review the plan above. Assessment runs only after you confirm.")
            return
        with st.spinner("Assessment + critic debate + prediction..."):
            st.session_state.result = runner.run_assessment(prep)
        result = st.session_state.result

    st.divider()

    # --- Readiness report (post human gate) ------------------------------
    a = result["assessment"]["assessment"]
    verdict = result["critic"]["verdict"]
    loops = result["loop_iterations_run"]
    # Color-coded verdict banner.
    _v = {"READY": (st.success, "✅ READY"),
          "NEEDS_ADJUSTMENT": (st.warning, "⚠️ NEEDS ADJUSTMENT"),
          "CRITICAL_GAPS": (st.error, "🔴 CRITICAL GAPS")}
    _fn, _label = _v.get(verdict, (st.info, verdict))
    _fn(f"### {_label} — {a['overall_score']}% overall  ·  {loops} feedback loop(s)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall score", f"{a['overall_score']}%", help="Mean of per-skill scores")
    c2.metric("Critic verdict", verdict)
    c3.metric("Feedback loops", loops)
    if loops > 1:
        st.caption(f"📈 Improved from {result['initial_score']}% to "
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

    # --- Fabric IQ ontology (semantic layer behind the insights) ----------
    onto = fabric_iq.ontology()
    if onto:
        with st.expander("🧩 Fabric IQ — Semantic Ontology (entities · relationships · rules)"):
            st.caption("The shared business semantics driving planning, analytics, and agents.")
            st.markdown("**Entities:** " + ", ".join(e["name"] for e in onto.get("entities", [])))
            st.markdown("**Relationships:**")
            for r in onto.get("relationships", []):
                st.markdown(f"- `{r['from']}` → **{r['type']}** → `{r['to']}`")
            st.markdown("**Business rules:**")
            for r in onto.get("rules", []):
                st.markdown(f"- **{r['id']}** — {r['description']}")


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
# Reliability & Safety view
# ---------------------------------------------------------------------------
def reliability_view():
    st.subheader("🛡️ Reliability & Safety")
    st.caption("Evaluation, Responsible-AI guardrails, and telemetry — the "
               "evidence that CertForge is accurate, safe, and observable.")

    if st.button("📏 Run Evaluation (all 15 learners)", type="primary"):
        with st.spinner("Evaluating against ground-truth outcomes..."):
            st.session_state.eval = evaluate.evaluate_all()

    ev = st.session_state.get("eval")
    if ev:
        acc = ev["predictive_accuracy"]
        st.markdown("#### 1. Predictive Accuracy (leave-one-out vs actual outcomes)")
        c = st.columns(4)
        c[0].metric("Accuracy", acc["accuracy"])
        c[1].metric("Precision", acc["precision"])
        c[2].metric("Recall", acc["recall"])
        c[3].metric("F1", acc["f1"])
        st.caption(f"{acc['correct']}/{acc['total']} correct · {acc['method']}")

        g, s, f = ev["groundedness"], ev["safety"], ev["fairness"]
        st.markdown("#### 2. Groundedness & Safety")
        c = st.columns(3)
        c[0].metric("Question citations", g["avg_question_citation_ratio"])
        c[1].metric("Curator citations", g["curator_citation_rate"])
        c[2].metric("Output guardrail pass", s["output_guardrail_pass_rate"])

        st.markdown("#### 3. Fairness (predicted pass rate by role)")
        st.write(f["predicted_pass_rate_by_role"])
        flag = "🟢 OK" if f["flag"] == "ok" else "🟡 REVIEW"
        st.caption(f"Max disparity across roles: {f['max_disparity']} → {flag}")

    st.divider()
    st.markdown("#### 🔬 Live-mode Evaluation (real LLM path)")
    st.caption("Validates the *live* agents (Foundry `gpt-oss-120b`): did they use the "
               "LLM, ground via the managed Foundry IQ KB, return valid verdicts, and "
               "pass guardrails. ⚠️ Slow (~2–4 min for 1 learner — gpt-oss reasoning).")
    if st.button("🔬 Run Live-mode Eval (1 learner)"):
        with st.spinner("Running the full pipeline on the live LLM... (~2–4 min)"):
            st.session_state.live_eval = evaluate.evaluate_live(["EMP-001"])
    le = st.session_state.get("live_eval")
    if le and not le.get("error"):
        lc = st.columns(4)
        lc[0].metric("LLM-powered", f"{int(le['llm_powered_rate']*100)}%")
        lc[1].metric("Foundry IQ grounding", f"{int(le['avg_foundry_iq_grounding']*100)}%")
        lc[2].metric("Verdict validity", f"{int(le['verdict_validity']*100)}%")
        lc[3].metric("Avg latency", f"{le['avg_seconds']}s")
        st.caption(f"Engine: {le['per_learner'][0]['engine'] if le.get('per_learner') else '—'} "
                   f"· guardrail pass {int(le['guardrail_pass_rate']*100)}%")
    elif le:
        st.info(le["error"])

    st.divider()
    st.markdown("#### 4. Telemetry (recent runs)")
    traces = telemetry.read_traces(10)
    if traces:
        st.dataframe(pd.DataFrame([
            {"time": t["timestamp"][11:19], "learner": t.get("employee_id"),
             "cert": t.get("certification"), "engine": t["engine"],
             "loops": t["loop_iterations"], "secs": t["total_agent_seconds"],
             "verdict": t.get("verdict"), "guardrail": "✅" if t.get("guardrail_passed") else "❌"}
            for t in reversed(traces)
        ]), use_container_width=True, hide_index=True)
    else:
        st.info("No telemetry yet — run a learner or team analysis first.")

    st.divider()
    st.markdown("#### 🛡️ Adversarial Safety Tests (Responsible AI — *Discover*)")
    suite = guardrails.run_safety_suite()
    st.caption(f"Input guardrail vs. red-team prompts: **{suite['passed']}/{suite['total']} "
               f"handled correctly** (PII, prompt injection, out-of-scope, real names).")
    st.dataframe(pd.DataFrame([
        {"Case": c["case"], "Expected": c["expected"], "Actual": c["actual"],
         "✓": "✅" if c["passed"] else "❌"} for c in suite["cases"]
    ]), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 🤝 Transparency")
    st.warning(guardrails.TRANSPARENCY_NOTICE)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
st.markdown(
    "<h1 style='margin-bottom:0'>🎓 CertForge</h1>"
    "<p style='color:#5b6770; font-size:1.05rem; margin-top:0.2rem'>"
    "An 8-agent certification-intelligence system that <b>debates your readiness, "
    "predicts your outcome, and gets smarter with every learner.</b></p>",
    unsafe_allow_html=True)
st.caption("Microsoft Foundry · all 3 IQ layers · synthetic data only, for demonstration")

# Sidebar: branding + engine + IQ-layer status.
mode = "🟢 MOCK (local, instant)" if config.use_mock() else f"☁️ Foundry · {config.chat_model()}"
st.sidebar.markdown("### 🎓 CertForge")
st.sidebar.markdown(f"**Engine:** {mode}")
st.sidebar.markdown(
    f"**IQ layers:** Foundry IQ {'🟢' if config.foundry_iq_enabled() else '⚪'} · "
    f"Fabric IQ 🟢 · Work IQ 🟢")
st.sidebar.markdown("---")
view = st.sidebar.radio(
    "View", ["👤 Learner", "📊 Manager", "🔍 Reasoning Trace", "🛡️ Reliability"])
st.sidebar.markdown("---")
st.sidebar.caption("⚠️ AI decision-support — a human reviews readiness decisions. "
                   "Synthetic data only, for demonstration.")

if view.startswith("👤"):
    learner_view()
elif view.startswith("📊"):
    manager_view()
elif view.startswith("🔍"):
    trace_view()
else:
    reliability_view()
