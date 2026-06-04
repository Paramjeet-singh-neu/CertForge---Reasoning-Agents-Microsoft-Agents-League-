# 🎓 CertForge

**An 8-agent enterprise certification-intelligence system for the Agents League — Reasoning Agents track (Microsoft Foundry).**

CertForge helps organisations run team certification programmes. It plans, engages,
assesses, *debates*, predicts, loops, and learns — using multiple Microsoft IQ
layers and procedural memory. It doesn't just answer "are you ready?" — it argues
the case from evidence, predicts your outcome, simulates what-if scenarios, and
gets smarter with every learner.

> ⚠️ **Synthetic data only.** All learners, work signals, and documents are
> fabricated (IDs like `L-1001`, `EMP-001`, `TEAM-A`). No real people, no PII.
> For demonstration only.

---

## Architecture

```
Learner ─▶ Orchestrator (plan + memory recall + feedback-loop control)
              │
   ┌──────────┼───────────────┬──────────────────┐   (parallel)
   ▼          ▼               ▼                  ▼
 Curator   Study Plan    Engagement      Pattern Analyst
 (Foundry  (Fabric IQ)   (Work IQ)       (historical evidence)
  IQ+MCP)                                       │
   └──────────┴───────────────┴──────────────────┘
              ▼  (sequential reasoning)
        Assessment (self-reflection)
              ▼
        Readiness Critic (devil's advocate, evidence-backed)
              ▼
        Outcome Predictor (3 scenarios + what-if model)
              │
     ┌────────┴─────────┐
   READY            NOT READY ──▶ FEEDBACK LOOP (re-plan weak areas, max 3×)
     ▼
 Career Pathway ─▶ Manager Insights (individual + team) ─▶ Procedural Memory
```

### The 8 agents + synthesizer

| Agent | Role | Grounding |
|-------|------|-----------|
| Orchestrator | Plan, recall memory, control the feedback loop | Procedural Memory |
| Learning Path Curator | Map cert → cited learning modules | Foundry IQ + MS Learn MCP |
| Study Plan Generator | Capacity-aware week-by-week schedule | Fabric IQ |
| Engagement Agent | Study windows + capacity-risk flags | Work IQ |
| Performance Pattern Analyst | Pass/fail patterns + what-if coefficients | Foundry IQ + Fabric IQ |
| Assessment Agent | Grounded, cited questions + **self-reflection** | Foundry IQ + Fabric IQ |
| Readiness Critic | Challenge claims with **pattern evidence** | (consumes all) |
| Outcome Predictor | 3 weighted scenarios + what-if simulator model | (consumes Pattern Analyst) |
| Manager Insights | Individual report + team risk dashboard | Work IQ + Fabric IQ |

### Capability layers
1. **Feedback loop** — re-plans weak areas and re-runs assessment→critic→predictor (max 3×).
2. **What-If simulator** — live recompute of pass probability as you adjust hours/exams/slot.
3. **Career pathway** — next certification preview when READY.
4. **Team batch mode** — process a whole team into a manager dashboard.
5. **Reasoning trace viewer** — every agent's decision chain, inspectable.

### Reasoning patterns demonstrated
Planner–Executor · Critic/Verifier · Self-reflection · Role specialisation · Feedback loop.

---

## Microsoft IQ integration
- **Foundry IQ** — grounded, cited content for the Curator & Assessment agents.
- **Fabric IQ** — the semantic model (`data/semantic_model.json`): role → cert → skills → hours → threshold → prerequisite.
- **Work IQ** — work signals (`data/work_signals.json`): meeting/focus hours, preferred slot, team.

---

## Running locally

```bash
# from the repo root
python3 -m venv .venv && source .venv/bin/activate
pip install -r certforge/requirements.txt

# run the test suite
python -m pytest certforge/tests/ -q

# launch the dashboard (added in the UI phase)
streamlit run certforge/src/ui/app.py
```

### Mock vs. Azure
CertForge runs in two modes, controlled by `CERTFORGE_MOCK` in `certforge/.env`:
- `true` (default) — agents use local deterministic logic. No Azure, no cost. Demo-safe.
- `false` — agents call real Azure AI Foundry models. (Wired up in the Azure phase.)

Copy `.env.example` → `certforge/.env` and fill in Azure values when ready.

---

## Project layout
```
certforge/
  data/            synthetic learners / work signals / semantic model
  knowledge/       Foundry IQ knowledge documents
  src/
    config.py      config + cached data loaders
    agents/        the 8 agents + base contract + manager synthesizer
    pipeline/      the orchestration runner (parallel + sequential + loop)
    memory/        procedural memory store
    ui/            Streamlit dashboard
  tests/           pipeline regression tests
```
