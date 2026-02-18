# Azure Well-Architected + Azure AI Landing Zones Alignment (Portfolio)

This repo is a **portfolio/demo** project, not a full enterprise landing zone. The goal is to show
production-oriented patterns that map to the Azure Well-Architected Framework (WAF) and the
Azure AI Landing Zones reference.

Key reference:
- Azure AI Landing Zones: https://github.com/Azure/AI-Landing-Zones

## Azure Well-Architected Framework (WAF)

### Security

Implemented:
- **Identity-first data access**: Cosmos DB is accessed using **Managed Identity + Cosmos RBAC**.
  - IaC: `infra/azure/main.bicep` (`sqlRoleAssignments`, `COSMOS_USE_MANAGED_IDENTITY=true`)
  - App: `src/chatbot_parking/persistence.py` (`DefaultAzureCredential`)
- **Secret handling**: deployment uses Container Apps secrets and GitHub OIDC (no long-lived Azure credentials).
  - CD: `.github/workflows/cd-azure-containerapps.yml`
- **Web hardening**:
  - Admin endpoints require `x-api-token` (`ADMIN_UI_TOKEN`)
  - API docs disabled in prod (`/docs`, `/redoc`, `/openapi.json` -> 404)
  - `TrustedHostMiddleware` enabled in prod (allow-list via `ALLOWED_HOSTS`)
  - Rate limiting in prod
  - Webhook verification (Slack anti-replay + signature; WhatsApp signature when configured)
  - Code: `src/chatbot_parking/web_demo_server.py`, `src/chatbot_parking/http_security.py`

Follow-ups (not implemented by default here):
- Front Door + WAF in front of the UI/API (bot protection, global edge, DDoS posture)
- Private networking (VNet integration / Private Endpoints) for Cosmos + Storage
- Key Vault for secret lifecycle management (instead of app secrets)

### Reliability

Implemented:
- **Durable workflow** for booking turns (serverless orchestration, retry-friendly).
  - Azure Functions: `infra/azure/durable_functions/*`
- **State persistence** in Cosmos (threads, approvals, reservations).
  - `src/chatbot_parking/persistence.py`
- Defensive timeouts:
  - Durable polling timeout in UI service (`DURABLE_POLL_TIMEOUT`)

Follow-ups:
- Multi-region DR patterns (not required for this demo)
- SLOs + alerting based on App Insights metrics

### Cost Optimization

Implemented:
- Container App scale: `minReplicas=0`, `maxReplicas=1` (demo budget)
  - IaC: `infra/azure/main.bicep`
- ACR Basic SKU (portfolio-friendly)
- Subscription budget `$10` + best-effort “kill switch”
  - IaC: `infra/azure/subscription_budget_autostop.bicep`
- Teardown script to avoid ongoing spend:
  - `scripts/azure/teardown.sh`

### Operational Excellence

Implemented:
- CI + CD with smoke test after deploy
  - `.github/workflows/ci.yml`
  - `.github/workflows/cd-azure-containerapps.yml`
  - `scripts/smoke_test_cloud.sh`
- “Version proof” endpoint + UI build stamp
  - `GET /version` in `src/chatbot_parking/web_demo_server.py`
- Azure inventory script
  - `scripts/azure/inventory.sh`

### Performance Efficiency

Implemented:
- Chunking for better retrieval and bounded context size
  - `src/chatbot_parking/rag.py`
- Deterministic “echo mode” to avoid hard failure when LLM quota is unavailable
  - `src/chatbot_parking/rag.py`, `src/chatbot_parking/interactive_flow.py`

Follow-ups:
- Caching hot answers + embedding caching
- Async batching / queue-based ingestion for large docs

## OWASP LLM Top 10 (High-Level)

See: `docs/guardrails.md`

Highlights:
- Prompt-injection and system-prompt request detection (`src/chatbot_parking/guardrails.py`)
- Sensitive-data filtering (regex + optional ML/NER)
- Tool boundary enforced by MCP and explicit gates (confirmation + admin approval)
- Output handling avoids executing model output

## Azure AI Landing Zones (ALZ) Concepts Used

Implemented (portfolio scale):
- Workload separation: UI/API vs orchestration (Container Apps + Durable Functions)
- Identity-first access to data (Managed Identity + RBAC)
- IaC (Bicep) and GitHub OIDC
- Cost guardrails (budget + stop endpoint)

Not implemented (enterprise scope):
- Full “platform landing zone” with policy-as-code at scale (Azure Policy initiatives)
- Centralized networking (hub/spoke), private DNS, private endpoints by default
- Enterprise secret governance and rotation policies

