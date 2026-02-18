# Production Deployment Runbook (Azure Hybrid: Container Apps + Durable Functions)

This repo deploys a portfolio-ready hybrid architecture on Azure:

- **UI/API (Container App)** serves `/chat/ui`, `/admin/ui`, and `/chat/message`.
- **Durable Functions** runs the booking workflow turn as an activity.
- **Cosmos DB (SQL API)** persists threads + approvals + reservations (no in-memory loss).
- **MCP stdio tool server** records approved reservations (stdio transport inside the UI container).
- **Cost controls** include a `$10` budget + best-effort stop endpoint.

## Prerequisites (Local Machine)

- `az` (Azure CLI) with Bicep support: `az bicep version`
- `gh` (GitHub CLI): `gh auth status`
- `jq` (used by `scripts/smoke_test_cloud.sh`)
- Python `3.12` for local tests (optional for deploy-only)

## 1) Provision Azure Infrastructure (IaC)

Create a resource group (example):

```bash
az group create -n rg-chatbot-parking-v2 -l eastus
```

Deploy `infra/azure/main.bicep`:

```bash
az deployment group create \
  --resource-group rg-chatbot-parking-v2 \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/main.parameters.json
```

Verify endpoints and the resource inventory:

```bash
bash scripts/azure/inventory.sh rg-chatbot-parking-v2
```

## 2) (Optional) Budget Auto-Stop Guardrail ($10)

This repo includes a subscription-level budget that triggers an Action Group webhook which calls:
- Durable Function endpoint: `POST /api/budget/stop`

Deploy:

```bash
az deployment sub create \
  --location eastus \
  --template-file infra/azure/subscription_budget_autostop.bicep \
  --parameters @infra/azure/subscription_budget_autostop.parameters.json
```

Notes:
- Cost budgets can lag; this is best-effort only.
- Stopping compute reduces spend, but some resources still bill (for example: ACR storage, Cosmos storage).

## 3) Configure GitHub Actions (OIDC + Secrets + Vars)

### GitHub Variables (repo-level)

- `AZURE_ACR_NAME` (example: `chatbotparkingacr`)
- `AZURE_RESOURCE_GROUP` (example: `rg-chatbot-parking-v2`)
- `AZURE_FUNCTIONAPP_NAME` (example: `chatbot-parking-func`)

Set via `gh`:

```bash
gh variable set AZURE_ACR_NAME --body "chatbotparkingacr"
gh variable set AZURE_RESOURCE_GROUP --body "rg-chatbot-parking-v2"
gh variable set AZURE_FUNCTIONAPP_NAME --body "chatbot-parking-func"
```

### GitHub Secrets (repo-level)

Required:
- `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` (for `azure/login` OIDC)
- `ADMIN_UI_TOKEN` (protects admin API + UI actions via `x-api-token`)
- `SESSION_SECRET_KEY` (cookie/session signing key; required in `APP_ENV=prod`)
- `OPENAI_API_KEY` (LLM + optional server-side dictation transcription)

Optional (enables GitHub OAuth login in UI):
- `OAUTH_GITHUB_CLIENT_ID`
- `OAUTH_GITHUB_CLIENT_SECRET`

Set via `gh` (example commands; values are read from stdin by default):

```bash
gh secret set AZURE_CLIENT_ID
gh secret set AZURE_TENANT_ID
gh secret set AZURE_SUBSCRIPTION_ID
gh secret set ADMIN_UI_TOKEN
gh secret set SESSION_SECRET_KEY
gh secret set OPENAI_API_KEY
```

## 4) Deploy (CD)

CD workflow: `.github/workflows/cd-azure-containerapps.yml`

Triggers:
- On push to `main`
- Manual run via `workflow_dispatch`

Monitor:

```bash
gh run list --workflow cd-azure-containerapps.yml --limit 5
gh run watch --workflow cd-azure-containerapps.yml
```

## 5) Post-Deploy Validation

1. Confirm UIs:

```bash
FQDN="$(az containerapp show -g rg-chatbot-parking-v2 -n chatbot-parking-ui --query 'properties.configuration.ingress.fqdn' -o tsv)"
BASE_URL="https://${FQDN}"
curl -fsSL "$BASE_URL/chat/ui" >/dev/null
curl -fsSL "$BASE_URL/admin/ui" >/dev/null
curl -fsSL "$BASE_URL/version"
```

2. Retrieve admin token (do not paste into chat):

```bash
az containerapp secret list -g rg-chatbot-parking-v2 -n chatbot-parking-ui --show-values \
  --query "[?name=='admin-ui-token'].value" -o tsv
```

3. Run the full smoke test (booking -> approve -> recorded):

```bash
FQDN="$(az containerapp show -g rg-chatbot-parking-v2 -n chatbot-parking-ui --query 'properties.configuration.ingress.fqdn' -o tsv)"
ADMIN_TOKEN="$(az containerapp secret list -g rg-chatbot-parking-v2 -n chatbot-parking-ui --show-values --query \"[?name=='admin-ui-token'].value\" -o tsv)"
BASE_URL="https://${FQDN}" ADMIN_TOKEN="$ADMIN_TOKEN" ./scripts/smoke_test_cloud.sh
```

## 6) Managed Identity (Cosmos Keyless)

This deployment is designed to use **Cosmos RBAC + Managed Identity**:

- `COSMOS_USE_MANAGED_IDENTITY=true`
- No Cosmos keys are required in app settings.

If Cosmos access fails, see `docs/quota_support_payload.md` for troubleshooting patterns.

## 7) Tear Down (Avoid Ongoing Cost)

Delete the resource group (and optionally the budget/action group):

```bash
bash scripts/azure/teardown.sh rg-chatbot-parking-v2
```
