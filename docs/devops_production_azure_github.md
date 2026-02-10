# Production Readiness (Azure + GitHub)

This guide documents a production-oriented deployment approach for the parking chatbot services on Azure using GitHub Actions.

## What was added

- GitHub CI workflow for tests on pull requests and pushes.
- GitHub CD workflow for Azure Container Apps deployment via OIDC.
- Hardened production Dockerfile running as non-root.
- Azure Bicep baseline for ACR + Container Apps + Log Analytics.
- Health endpoints for liveness probes.

## 1) Prerequisites

- Azure subscription.
- Existing resource group.
- GitHub repository with Actions enabled.
- Azure CLI (`az`) and Bicep support installed.

## 2) Provision infrastructure

Deploy the infrastructure template from `infra/azure/main.bicep`:

```bash
az deployment group create \
  --resource-group <resource-group> \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/main.parameters.json
```

After deployment, capture outputs (`adminApiUrl`, `mcpServerUrl`, `acrLoginServer`).

## 3) Configure GitHub OIDC for Azure login

Create an Entra ID application/service principal with federated credentials for your GitHub org/repo and environment/branch policy.

Store these repository secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `ADMIN_API_TOKEN`
- `MCP_API_TOKEN`

Store these repository variables:

- `AZURE_ACR_NAME`
- `AZURE_RESOURCE_GROUP`
- `AZURE_CONTAINERAPP_ENV`

## 4) CI/CD flow

### CI (`.github/workflows/ci.yml`)

- Runs on pull requests and pushes to `main`.
- Installs dependencies and runs `pytest -q`.

### CD (`.github/workflows/cd-azure-containerapps.yml`)

- Runs on pushes to `main` or manual dispatch.
- Authenticates to Azure using OIDC (`azure/login@v2`).
- Builds images with `az acr build` and tags with commit SHA + `latest`.
- Updates both container apps with the new image.

## 5) Runtime hardening notes

- Image uses `python:3.11-slim`.
- Container runs as an unprivileged user (`uid=10001`).
- `.dockerignore` excludes local and sensitive artifacts from build context.
- Azure Container Apps are configured with min/max replicas and liveness probes.

## 6) Post-deploy validation

Use health endpoints:

- Admin API: `GET /admin/health`
- MCP Server: `GET /health`

Example:

```bash
curl -fsS https://<admin-fqdn>/admin/health
curl -fsS https://<mcp-fqdn>/health
```

## 7) Recommended next steps (optional)

- Move `MCP_API_TOKEN` and `ADMIN_API_TOKEN` to Azure Key Vault and reference managed secrets.
- Add branch protection requiring `CI` workflow success.
- Add image vulnerability scanning (e.g., Trivy or Defender for Cloud).
- Add staging environment with required approvals before production deployment.
