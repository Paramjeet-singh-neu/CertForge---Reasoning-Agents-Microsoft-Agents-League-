# 🏗️ CertForge — Architecture

How CertForge uses **Microsoft Foundry** end to end: a Hosted Agent on Foundry
Agent Service runs an 8-agent reasoning pipeline, grounded by all three Microsoft
IQ layers, calling Foundry models, with evaluation, Responsible-AI guardrails, and
Application Insights observability.

```mermaid
flowchart TB
    subgraph Users[" "]
        L["👤 Learner — role, target cert, topics"]
        M["📊 Manager"]
    end

    subgraph FAS["☁️ Foundry Agent Service — Hosted Agent (managed identity, dedicated endpoint)"]
        direction TB
        ORC["🧠 Orchestrator / Dispatcher<br/>(plan · memory recall · loop control)"]
        subgraph PAR["Parallel analysis"]
            CUR["📚 Learning Path Curator"]
            SP["📅 Study Plan Generator"]
            ENG["🗓️ Engagement Agent"]
            PA["📊 Pattern Analyst (deterministic)"]
        end
        GATE{{"🧑‍⚖️ Human-in-the-loop<br/>Ready to be assessed?"}}
        ASM["✏️ Assessment (self-reflection)"]
        CRIT["⚖️ Readiness Critic (verdict guardrail)"]
        PRED["🔮 Outcome Predictor + What-If"]
        CP["🗺️ Career Pathway"]
        MI["📈 Manager Insights"]
        ORC --> CUR & SP & ENG & PA
        PAR --> GATE
        GATE -->|confirm| ASM --> CRIT --> PRED
        PRED -->|NOT READY| ORC
        PRED -->|READY| CP --> MI
    end

    subgraph IQ["Microsoft IQ layers (grounding & semantics)"]
        direction LR
        FIQ["🟢 Foundry IQ<br/>managed Azure AI Search KB<br/>agentic retrieval + citations"]
        FAB["🟢 Fabric IQ<br/>semantic ontology + rules<br/>(role→cert→skill→threshold)"]
        WIQ["🟢 Work IQ<br/>work-context signals<br/>(meetings, focus, capacity)"]
    end

    subgraph FND["Microsoft Foundry models (AIProjectClient)"]
        GPT["gpt-oss-120b (reasoning)"]
        EMB["text-embedding-3-small"]
    end

    MCP["🔌 MS Learn MCP server<br/>(real learn.microsoft.com URLs)"]
    MEM[("🧠 Procedural Memory")]

    subgraph OPS["Reliability & Observability"]
        EVAL["📏 Evaluation — 93% leave-one-out + live-mode"]
        GRD["🛡️ Guardrails + Adversarial suite (RAI)"]
        AI["📡 Application Insights (OpenTelemetry)"]
    end

    L --> ORC
    M --> MI
    CUR -. cites .-> FIQ
    ASM -. cites .-> FIQ
    CUR -. real URLs .-> MCP
    SP -. rules .-> FAB
    CP -. prereq rule .-> FAB
    MI -. semantics .-> FAB
    ENG -. signals .-> WIQ
    FIQ --- EMB
    ASM -. judgment .-> GPT
    CRIT -. judgment .-> GPT
    ORC <-.-> MEM
    FAS --> AI
    FAS --> EVAL
    FAS --> GRD
```

### Legend
- **Hosted Agent** (Foundry Agent Service): the entry agent + 8 sub-agents, deployed
  as a container with a managed Entra identity and a dedicated endpoint.
- **Foundry IQ**: managed Azure AI Search knowledge base — Curator & Assessment
  retrieve cited passages via the `knowledge_base_retrieve` MCP tool (managed-identity auth).
- **Fabric IQ**: the semantic ontology (entities, relationships, business rules)
  driving planning, the prerequisite/readiness rules, and manager insights.
- **Work IQ**: work-context signals → study windows, capacity-risk, adaptive reminders.
- **Models**: `gpt-oss-120b` (agent reasoning) + `text-embedding-3-small` via the
  unified `AIProjectClient`.
- **Reliability**: leave-one-out + live-mode evaluation, Responsible-AI guardrails +
  adversarial safety suite, and OpenTelemetry → Application Insights.

> Provider-agnostic by design: the same code runs on GitHub Models (`LLM_PROVIDER=github`)
> and falls back to a deterministic mock engine — demo-safe with no hard dependency.
