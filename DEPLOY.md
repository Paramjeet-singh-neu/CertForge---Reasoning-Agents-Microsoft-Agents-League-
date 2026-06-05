# 🚀 CertForge — Hosted Deployment Story (Foundry Agent Service)

CertForge is built to deploy as a **Hosted Agent in Microsoft Foundry Agent
Service** — Microsoft's managed platform for containerised agent code. This
document is the complete deployment path; the agent already conforms to the
Hosted Agent runtime contract and runs locally today.

---

## What's already in place

| Piece | File | Status |
|-------|------|--------|
| Hosted Agent entrypoint (Responses + Invocations protocols, port 8088, `/healthz`) | [certforge/agent/main.py](certforge/agent/main.py) | ✅ runs locally |
| Agent version definition (protocols, resources, env) | [certforge/agent/agent.yaml](certforge/agent/agent.yaml) | ✅ |
| Container image | [Dockerfile](Dockerfile) (python:3.13-slim) | ✅ |

The entrypoint exposes the two documented protocols:
- **Responses** — `POST /responses` `{"input","stream"}` (playground / OpenAI SDK clients).
- **Invocations** — `POST /invocations` (structured JSON in/out — fits our analysis).

---

## 1. Run & test locally (matches the quickstart)

```bash
pip install -r certforge/requirements.txt fastapi uvicorn
python certforge/agent/main.py        # listens on http://localhost:8088

# Responses protocol (natural language in)
curl -sS -H "Content-Type: application/json" -X POST http://localhost:8088/responses \
    -d '{"input": "Analyze EMP-001 for AZ-204", "stream": false}'

# Invocations protocol (structured)
curl -sS -H "Content-Type: application/json" -X POST http://localhost:8088/invocations \
    -d '{"employee_id":"EMP-009","certification":"AZ-204"}'
```

## 2. Build the container

```bash
docker build -t certforge:latest .
docker run -p 8088:8088 -e GITHUB_TOKEN=$GITHUB_TOKEN certforge:latest
```

## 3. Deploy to Foundry Agent Service

**Prerequisites** (per Microsoft's quickstart):
- A Foundry project with a **deployed model** (e.g. `gpt-4.1`).
- **Foundry Project Manager** role at project scope, plus **Owner / User Access
  Administrator** on the subscription (so `azd` can auto-assign the agent +
  ACR-pull roles).
- A **supported region**: East US 2, North Central US, Sweden Central, West US,
  West US 3, Canada Central/East, and others.
- Python 3.13+ and the Microsoft Foundry Toolkit for VS Code (or `azd` ≥ 1.25
  with the `azure.ai.agents` extension).

**Deploy (VS Code / Foundry Toolkit):**
1. Command Palette → **Foundry Toolkit: Create Project** (or reuse one).
2. **Foundry Toolkit: Open Model Catalog** → deploy `gpt-4.1`.
3. **Foundry Toolkit: Deploy Hosted Agent** → Deployment Method **Code**,
   package mode **Remote** → **Deploy**. Foundry builds the image, pushes it to
   Azure Container Registry, provisions compute, assigns an Entra agent identity,
   and exposes the endpoint.

**Deploy (CLI):**
```bash
azd auth login
azd ai agent init      # scaffolds from agent.yaml
azd deploy
azd ai agent invoke -d '{"input":"Analyze EMP-001 for AZ-204"}'
```

### Endpoints (after deploy)
- Responses: `{project_endpoint}/agents/certforge/endpoint/protocols/openai/responses`
- Invocations: `{project_endpoint}/agents/certforge/endpoint/protocols/invocations`

### Configuration & secrets
- Set per-version **environment variables** (immutable per version):
  `CERTFORGE_MOCK=false`, `LLM_PROVIDER`, `LLM_MODEL`.
- **Never bake secrets into the image.** Provide `GITHUB_TOKEN` via a **Key Vault
  connection**. To use the Foundry-hosted model instead of GitHub Models, set
  `LLM_PROVIDER=azure` — the agent then calls the deployed model with its Entra
  agent identity (no token needed).
- **Observability** is automatic: Foundry injects an Application Insights
  connection string; the protocol libraries emit OpenTelemetry traces.

---

## ✅ Deployed and running on Foundry Agent Service

CertForge **is deployed as a live Hosted Agent** (`certforge:1`, status *active*)
in a Foundry project in **Canada Central**, with its own Microsoft Entra agent
identity and a dedicated endpoint:

```
https://paramjeetsingh-hack-resource.services.ai.azure.com/api/projects/paramjeetsingh-hack/agents/certforge/endpoint/protocols/openai/responses?api-version=v1
```

The hosted agent runs **Assessment + Critic on `gpt-oss-120b`** via its managed
identity (no keys), returning the full readiness analysis. Verified:
`azd ai agent invoke certforge "Analyze EMP-001 for AZ-204" -o raw` → HTTP 200,
`engine: azure:gpt-oss-120b`, `llm_powered_agents: ["AssessmentAgent","ReadinessCritic"]`.

### How it was deployed
1. `az cognitiveservices account deployment create … gpt-oss-120b` (CLI deploy
   bypassed the portal region UI; **Canada Central** is the one region both
   allowed by the student policy *and* supported for hosted agents).
2. `azd ai agent init --no-prompt --project-id <project> --deploy-mode code
   --runtime python_3_13 --entry-point agent/main.py --src certforge`.
3. `azd env set AZURE_LOCATION eastus` (RG metadata region) — agent still hosts in
   Canada Central via the project.
4. `azd up`, then `azd deploy certforge` for code updates.

### Engineering notes (real constraints solved)
- The container `/app` is **read-only** → runtime writes go to `CERTFORGE_STATE_DIR`
  (`/tmp`) and are best-effort.
- The runtime probes **`GET /readiness`** (must return 200).
- `gpt-oss-120b` is a **reasoning model**: slow (~20s/call) and sometimes wraps
  JSON in a `{"final": …}` envelope (handled by `llm._unwrap`). The full 3-loop
  pipeline exceeds the request timeout, so the hosted path sets
  **`CERTFORGE_MAX_LOOPS=1`** (single-pass). Local/UI runs use the full 3 loops
  (also on Foundry — no request timeout there).
- Embeddings have 0 quota in Canada Central, so in-container retrieval uses the
  keyword fallback; local dev uses Foundry `text-embedding-3-small` (East US).

### Cost
Hosted agents **scale to zero after 15 min idle**, so standing cost is minimal.
To stop all charges when finished: delete the resource group
(`az group delete -n rg-31paramjeet.singh-6460`) or via the portal.
