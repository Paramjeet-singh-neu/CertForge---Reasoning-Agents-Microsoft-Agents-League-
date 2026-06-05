# 🎬 CertForge — Demo Script (~4 minutes)

A tight walkthrough that shows reasoning, all three IQ layers, the feedback loop,
and the reliability story. Run `streamlit run certforge/src/ui/app.py` first.

> Tip: set `CERTFORGE_MOCK=false` in `certforge/.env` for the live LLM demo
> (the Assessment + Critic "think" with gpt-4o-mini). Keep `true` for an instant,
> offline, demo-safe run. The sidebar badge shows which engine is active.

---

## 0. Framing (15s)
> "CertForge is an 8-agent system that doesn't just say whether you're ready for a
> certification — it **debates** it, **predicts** your outcome, and **gets smarter**
> with every learner. Everything here is synthetic data."

## 1. Learner View — the at-risk story (90s)
- Select **EMP-001**, target **AZ-204**, click **🚀 Analyse Readiness**.
- **Agent Activity** panel: point out the parallel agents, then the Assessment →
  Critic → Predictor chain, and the **🔄 feedback loop** firing.
- Talking points:
  - "The Critic **challenged** the assessment using historical evidence — only
    ~27% of similar learners passed."
  - "The feedback loop re-planned the weak areas and re-ran the chain — the score
    climbed **66% → 80%** and it converged to **READY**."
- Scroll to **skill bars**, **gamification**, **outcome prediction**.

## 2. What-If Simulator (30s)
- Drag **Additional study hours** and toggle **morning study**.
- "Pass probability recomputes **live** — using the *same* model the predictor
  used, so the demo number can't contradict the agent."

## 3. Career Pathway (15s)
- "Because EMP-001 reached READY, the system previews the next cert — **AZ-305** —
  sized to their work capacity."

## 4. Reasoning Trace (30s)
- Switch to **🔍 Reasoning Trace**.
- Expand the **Assessment** agent → show the **self-reflection** log.
- Expand the **Critic** → show the evidence-backed challenge.
- "Every decision is inspectable — full observability."

## 5. Manager View — team batch (45s)
- Switch to **📊 Manager**, click **👥 Run Team Analysis**.
- "One click processes the whole team into a **risk heatmap** — current standing,
  not the rosy post-study ending."
- Point out the **capacity alert** (EMP-004, 25 meeting hrs) and the
  **procedural-memory insights** aggregated across learners.

## 6. Reliability & Safety — the closer (45s)
- Switch to **🛡️ Reliability**, click **📏 Run Evaluation**.
- "We validate against **ground truth**: leave-one-out, **93% accuracy, 0.94 F1**."
- "Groundedness and output guardrails at 100%, and we **measure fairness** across
  roles — surfacing bias, not hiding it."
- Point to the **telemetry** table and the **transparency notice**.

---

## The three IQ layers (mention naturally)
- **Foundry IQ** — cited questions/content come from real retrieval over approved docs.
- **Fabric IQ** — the role→cert→skills→threshold semantic model drives planning.
- **Work IQ** — meeting/focus signals drive study windows and capacity risk.

## One-liner to close
> "Eight agents, three IQ layers, a feedback loop that argues with itself, and
> predictions validated at 93% — all running with a one-flag mock fallback so the
> demo never breaks."
