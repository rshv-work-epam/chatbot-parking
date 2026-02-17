# Production Readiness (Azure Hybrid: Container Apps + Durable Functions)

This guide documents a production-oriented deployment for the parking chatbot on Azure using GitHub Actions.

## What is deployed

- **UI/API Container App** (`chatbot-parking-ui`): serves `/chat/ui`, `/admin/ui`, `/chat/message`, and `/admin/*`.
- **Durable Function App**: executes chat turns via `POST /api/chat/start`.
- **Cosmos DB SQL API (serverless)**: stores thread state, approval requests/decisions, reservation records.
- **ACR + Container Apps Environment + Log Analytics + App Insights**.

## 1) Prerequisites

- Azure subscription and resource group.
- GitHub repository with Actions enabled.
- Azure CLI (`az`) with Bicep support.

## 2) Provision infrastructure

Deploy IaC from `infra/azure/main.bicep`:

```bash
az deployment group create \
  --resource-group <resource-group> \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/main.parameters.json
```

Capture outputs:

- `uiApiUrl`
- `durableBaseUrl`
- `acrLoginServer`
- `cosmosDbEndpoint`
- `cosmosDbDatabase`
- `cosmosDbThreadsContainer`
- `cosmosDbApprovalsContainer`
- `cosmosDbReservationsContainer`

## 2.1) (Optional) Budget auto-stop guardrail (best-effort)

This repo includes a budget-triggered "kill switch" endpoint in the Durable Function App (`/api/budget/stop`).
You can create a subscription-level Cost Management budget that triggers an Action Group, which calls that endpoint.

Files:

- Subscription-scope budget + action group: `infra/azure/subscription_budget_autostop.bicep`
- Example parameters: `infra/azure/subscription_budget_autostop.parameters.json`

Deploy at subscription scope:

```bash
az deployment sub create \
  --location <any-azure-region> \
  --template-file infra/azure/subscription_budget_autostop.bicep \
  --parameters @infra/azure/subscription_budget_autostop.parameters.json
```

Notes:

- This is best-effort only. Cost data and budget evaluation can lag, so it may not prevent you from exceeding $10.
- Stopping apps reduces compute spend, but some resources still bill when "stopped" (for example: ACR SKU, storage capacity).

## 3) Configure GitHub OIDC and repository settings

Secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `ADMIN_UI_TOKEN`
Variables:

- `AZURE_ACR_NAME`
- `AZURE_RESOURCE_GROUP`
- `AZURE_FUNCTIONAPP_NAME`

## 4) CI/CD behavior

### CI (`.github/workflows/ci.yml`)

- Runs tests on push/PR.

### CD (`.github/workflows/cd-azure-containerapps.yml`)

- Builds and pushes `chatbot-parking-ui` image to ACR.
- Updates the UI container app.
- Deploys Durable Function code from `infra/azure/durable_functions`.

## 5) Runtime configuration

UI container expects:

- `DURABLE_BASE_URL`
- `DURABLE_FUNCTION_KEY`
- `COSMOS_DB_ENDPOINT`
- `COSMOS_DB_KEY`
- `COSMOS_USE_MANAGED_IDENTITY=true` (optional alternative to `COSMOS_DB_KEY`, requires Cosmos RBAC)
- `COSMOS_DB_DATABASE`
- `COSMOS_DB_CONTAINER_THREADS`
- `COSMOS_DB_CONTAINER_APPROVALS`
- `COSMOS_DB_CONTAINER_RESERVATIONS`
- `PERSISTENCE_BACKEND=cosmos`
- `ADMIN_UI_TOKEN`

Durable Function expects:

- Cosmos connection variables listed above.
- `PERSISTENCE_BACKEND=cosmos`

Optional HTTP hardening knobs (UI/API service):

- `RATE_LIMIT_ENABLED=true|false` (defaults to enabled in `APP_ENV=prod`)
- `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`
- `CSP_ENABLED=true|false`

## 6) Post-deploy validation

```bash
curl -fsS https://<ui-fqdn>/chat/ui
curl -fsS https://<ui-fqdn>/admin/ui
curl -fsS https://<ui-fqdn>/admin/health
```

Durable starter check:

```bash
curl -X POST https://<function-fqdn>/api/chat/start \
  -H 'x-functions-key: <function-key>' \
  -H 'Content-Type: application/json' \
  -d '{"message":"What are the parking hours?","thread_id":"smoke-1"}'
```

## 7) Smoke flow (end-to-end)

1. Open `https://<ui-fqdn>/chat/ui` and start booking.
2. Open `https://<ui-fqdn>/admin/ui`, enter `ADMIN_UI_TOKEN`, approve request.
3. Return to chat and send another message; expect `Confirmed and recorded.`.
4. Verify reservation item exists in Cosmos reservations container.

## 8) Recommended hardening follow-ups

- Move secret values to Key Vault and use managed identity.
- Add staged environments with approvals.
- Add vulnerability scanning to CD.
