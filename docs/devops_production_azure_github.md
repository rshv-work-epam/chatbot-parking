# Production Readiness (Azure Hybrid: Container Apps + Durable Functions)

This guide documents a production-oriented deployment for the parking chatbot on Azure using GitHub Actions.

## What is deployed

- **UI/API Container App** (`chatbot-parking-ui`): serves `/chat/ui`, `/admin/ui`, `/chat/message`, and `/admin/*`.
- **Durable Function App**: executes chat turns via `POST /api/chat/start`.
- **Cosmos DB SQL API (serverless)**: stores thread state, approval requests/decisions, reservation records.
- **MCP Container App** (`chatbot-parking-mcp`): compatibility endpoint for `/record`.
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
- `mcpServerUrl`
- `durableBaseUrl`
- `acrLoginServer`
- `cosmosDbEndpoint`
- `cosmosDbDatabase`
- `cosmosDbThreadsContainer`
- `cosmosDbApprovalsContainer`
- `cosmosDbReservationsContainer`

## 3) Configure GitHub OIDC and repository settings

Secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `ADMIN_UI_TOKEN`
- `ADMIN_API_TOKEN`
- `MCP_API_TOKEN`

Variables:

- `AZURE_ACR_NAME`
- `AZURE_RESOURCE_GROUP`
- `AZURE_FUNCTIONAPP_NAME`

## 4) CI/CD behavior

### CI (`.github/workflows/ci.yml`)

- Runs tests on push/PR.

### CD (`.github/workflows/cd-azure-containerapps.yml`)

- Builds and pushes `chatbot-parking-ui` and `chatbot-parking-mcp` images to ACR.
- Updates both container apps.
- Deploys Durable Function code from `infra/azure/durable_functions`.

## 5) Runtime configuration

UI container expects:

- `DURABLE_BASE_URL`
- `DURABLE_FUNCTION_KEY`
- `COSMOS_DB_ENDPOINT`
- `COSMOS_DB_KEY`
- `COSMOS_DB_DATABASE`
- `COSMOS_DB_CONTAINER_THREADS`
- `COSMOS_DB_CONTAINER_APPROVALS`
- `COSMOS_DB_CONTAINER_RESERVATIONS`
- `PERSISTENCE_BACKEND=cosmos`
- `ADMIN_UI_TOKEN`

Durable Function expects:

- Cosmos connection variables listed above.
- `PERSISTENCE_BACKEND=cosmos`

## 6) Post-deploy validation

```bash
curl -fsS https://<ui-fqdn>/chat/ui
curl -fsS https://<ui-fqdn>/admin/ui
curl -fsS https://<ui-fqdn>/admin/health
curl -fsS https://<mcp-fqdn>/health
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
