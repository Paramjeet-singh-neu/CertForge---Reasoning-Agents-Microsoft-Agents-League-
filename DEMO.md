# 🎬 CertForge — Demo Script (~5 minutes, timed)

A turnkey recording script. Two tabs open before you start:
- **Browser A** — the Streamlit app (`streamlit run certforge/src/ui/app.py` → http://localhost:8501)
- **Browser B** — the Azure Foundry portal ([ai.azure.com](https://ai.azure.com)), signed in

> **Engine for the demo:** keep `CERTFORGE_MOCK=true` in `certforge/.env` for the
> on-screen walkthrough (instant, reliable). Show **one** real Foundry run at the
> end (Reliability → Live-mode Eval, or the hosted endpoint). Don't run the whole
> UI live — gpt-oss is ~50s/step.

---

## 0:00 – 0:25 — Framing
> "CertForge is an **8-agent enterprise certification-intelligence system** on
> Microsoft Foundry. It doesn't just say whether you're ready for a cert — it
> **curates a plan, debates your readiness, predicts your outcome, loops to
> improve, and gets smarter with every learner**. Everything here is synthetic
> data. It runs on real Foundry services — a deployed Hosted Agent, Foundry IQ,
> and gpt-oss-120b."

Point at the sidebar: **engine + all three IQ layers (🟢🟢🟢)**.

## 0:25 – 2:00 — Learner View: the at-risk story + human-in-the-loop
1. Pick **EMP-001**, target **AZ-204**, type topics **"Storage, Monitoring"**.
2. Click **📋 Build Study Plan & Engagement**.
   - Open **🧠 Agent Activity** — narrate the parallel agents (Curator, Study Plan, Engagement, Pattern Analyst).
   - Open **📚 Learning Path** — "cited modules, with **real learn.microsoft.com URLs from the MS Learn MCP server**."
   - Open **🗓️ Work IQ → Engagement** — "Work IQ signals → capacity risk **HIGH** (22 meeting hrs), study windows, and an **adaptive reminder schedule**."
3. **Stop at the gate:** "Here's the **human-in-the-loop** checkpoint — *Ready to be assessed?* A human decides before assessment runs." Click **✅ Confirm ready → Run Assessment**.
4. Narrate the result:
   - The **color-coded verdict banner** (starts at risk, ends **✅ READY** after the loop).
   - "The **Readiness Critic debated** the assessment with historical evidence; the **feedback loop** re-planned weak areas and the score climbed **66% → 80%**."
   - **Skill bars**, **gamification**.

## 2:00 – 2:45 — What-If + Career Pathway
- **🔮 Outcome Prediction** (pass/borderline/fail) → drag the **What-If sliders** (hours, exams, morning) — "pass probability recomputes **live**, using the same model the predictor used."
- **🗺️ Career Pathway** — "Because they're READY, Fabric IQ's **prerequisite rule** clears the next step: **AZ-305**."

## 2:45 – 3:15 — Reasoning Trace
- Switch to **🔍 Reasoning Trace**. Expand **AssessmentAgent** (self-reflection) and **ReadinessCritic** (evidence-backed challenge). "Every decision is inspectable."

## 3:15 – 4:00 — Manager View
- Switch to **📊 Manager** → **👥 Run Team Analysis**.
- **Risk heatmap** (mixed 🟢🟡🔴 — pre-intervention standing), **capacity alert** (EMP-004), **procedural-memory pattern insights**, **recommended actions**.
- Open **🧩 Fabric IQ — Semantic Ontology** — "the entities, relationships, and **business rules** (readiness, prerequisite, capacity) behind every recommendation."

## 4:00 – 4:40 — Reliability & Safety
- Switch to **🛡️ Reliability** → **📏 Run Evaluation**.
  - "**93% leave-one-out accuracy** against real outcomes, 100% groundedness, and we **measure fairness across roles**."
- Scroll to **🛡️ Adversarial Safety Tests** — "PII, prompt injection, out-of-scope — all blocked. That's the Responsible-AI **Discover → Protect → Govern** flow."
- *(Optional, pre-run)* **🔬 Live-mode Eval** — "validated on the real LLM: 100% LLM-powered, 100% Foundry IQ grounding." Point at the **telemetry** table + **transparency notice**.

## 4:40 – 5:00 — The real Azure services (Browser B — the closer)
Switch to the Foundry portal and show, quickly:
1. **Build → Agents → `certforge`** → status **active**, own identity → *"a live Hosted Agent on Foundry Agent Service."* (Optional: Open in playground, send "Analyze EMP-001 for AZ-204".)
2. **Build → Knowledge → `certforge-kb`** → *"the managed Foundry IQ knowledge base — Azure AI Search over our approved docs."*
3. **App Insights `certforge-ai` → Investigate → Performance** → *"real OpenTelemetry traces from the hosted agent."*

> **Close:** "Eight agents, all three Microsoft IQ layers, a feedback loop that
> argues with itself, a human-in-the-loop gate, predictions validated at 93% —
> deployed as a managed, identity-secured Hosted Agent on Microsoft Foundry."

---

## The three IQ layers (mention naturally as you go)
- **Foundry IQ** — managed Azure AI Search KB; cited grounding for Curator + Assessment.
- **Fabric IQ** — the semantic ontology (role→cert→skills→threshold→prereq) + business rules.
- **Work IQ** — meeting/focus signals → study windows, capacity risk, reminders.

## If you want a single hosted-agent proof on camera
```bash
azd ai agent invoke certforge "Analyze EMP-001 for AZ-204" -o raw
```
→ HTTP 200, `engine: azure:gpt-oss-120b`, full readiness JSON with Foundry IQ citations.
