# Production Readiness (Azure + GitHub)

This guide documents a production-oriented deployment approach for the parking chatbot services on Azure using GitHub Actions.

## What was added

- GitHub CI workflow for tests on pull requests and pushes.
- GitHub CD workflow split by GitHub Environments (`dev` and `prod`) using OIDC.
- Azure Bicep provisioning for environment-specific deployments.
- Azure Key Vault-managed app secrets with managed identity access.
- WAF-capable Azure Application Gateway in front of backend apps.
- Azure observability baseline with Log Analytics, Application Insights, and diagnostic settings.

## 1) Prerequisites

- Azure subscription.
- Existing resource group(s), ideally one per environment.
- GitHub repository with Actions enabled.
- Azure CLI (`az`) and Bicep support installed.

## 2) Provision infrastructure per environment

Deploy the infrastructure template from `infra/azure/main.bicep` using dedicated parameter files:

```bash
# Dev
az deployment group create \
  --resource-group <dev-resource-group> \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/main.dev.parameters.json

# Prod
az deployment group create \
  --resource-group <prod-resource-group> \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/main.prod.parameters.json
```

After deployment, capture outputs:

- `adminApiUrl`
- `mcpServerUrl`
- `wafPublicIp`
- `keyVaultName`
- `applicationInsightsConnectionString`
- `acrLoginServer`

## 3) Configure GitHub Environments and secrets

Create two GitHub environments:

- `dev`
- `prod`

In each environment, configure the following secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

Configure the following environment variables:

- `AZURE_ACR_NAME`
- `AZURE_RESOURCE_GROUP`

> Runtime application tokens (`ADMIN_API_TOKEN`, `MCP_API_TOKEN`) are no longer injected via GitHub Action environment variables. They are stored and consumed from Azure Key Vault through managed identities.

## 4) CI/CD flow

### CI (`.github/workflows/ci.yml`)

- Runs on pull requests and pushes to `main`.
- Installs dependencies and runs `pytest -q`.

### CD (`.github/workflows/cd-azure-containerapps.yml`)

- Runs automatically for:
  - `develop` branch → deploys to `dev` environment.
  - `main` branch → deploys to `prod` environment.
- Supports manual dispatch with explicit `target_environment` selection.
- Authenticates to Azure using OIDC (`azure/login@v2`).
- Builds images with `az acr build` and tags with commit SHA + `latest`.
- Updates environment-specific container apps.

## 5) Security baseline details

- **WAF:** Azure Application Gateway WAF_v2 with OWASP 3.2 rule set.
  - `prod` uses `Prevention` mode.
  - `dev` uses `Detection` mode.
- **Secrets:** Azure Key Vault stores API tokens. Container Apps retrieve secrets using system-assigned managed identity + `Key Vault Secrets User` RBAC role.
- **Registry hardening:** ACR admin user remains disabled; Container Apps use `AcrPull` role assignments.

## 6) Observability baseline details

- **Logs:** Container Apps environment logs go to Log Analytics.
- **Metrics/diagnostics:** Diagnostic settings capture platform logs and metrics for Container Apps and Application Gateway.
- **APM:** Application Insights is provisioned and connection string injected into each container app.

## 7) Post-deploy validation

Use health endpoints directly or through WAF path routing:

```bash
# Direct app checks
curl -fsS https://<admin-fqdn>/admin/health
curl -fsS https://<mcp-fqdn>/health

# Via App Gateway/WAF
curl -fsS http://<waf-public-ip>/admin/health
curl -fsS http://<waf-public-ip>/mcp/health
```

## 8) Recommended next steps

- Bind a trusted TLS certificate and custom domain to Application Gateway listener.
- Add private endpoints/network restrictions for Key Vault and Container Apps ingress.
- Enable Microsoft Defender for Cloud plans and container image vulnerability scanning policies.
- Add approval gates in the `prod` GitHub environment.
