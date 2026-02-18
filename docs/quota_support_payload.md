# Quota / Capacity Troubleshooting + Support Ticket Payload (Azure)

This repo can run in multiple modes:

- **Booking flow** does not require an LLM to function (slot-filling + validation + admin approval).
- **Info Q&A (RAG)** may require an LLM/embeddings provider (OpenAI/Azure OpenAI/Gemini), depending on configuration.

If you hit quotas (or provider outages), this doc helps you:
1. Identify what is failing.
2. Collect a minimal evidence pack.
3. Prepare a support-ticket payload for a quota increase.

## 1) Quick Checks (Always Do First)

### 1.1 Confirm you are on the latest deployment

- `GET https://<ui-fqdn>/version`
- The UIs show a `Build: sha ...` stamp in the header.

### 1.2 Check container logs

```bash
az containerapp logs show -g <rg> -n chatbot-parking-ui --tail 200
```

### 1.3 Check Durable Function starter (booking backend)

```bash
FUNC="https://<function-app>.azurewebsites.net"
KEY="<function-key>"

curl -fsSL -X POST "${FUNC}/api/chat/start" \
  -H "x-functions-key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"message":"I want to reserve a spot","thread_id":"quota-smoke"}'
```

## 2) Common Quota/Capacity Failure Modes

### A) OpenAI / Azure OpenAI quota

Symptoms:
- 429 errors (rate limit or insufficient quota)
- “You exceeded your current quota”
- Azure OpenAI “No capacity” (region/deployment capacity)

Impact on this app:
- `/chat/message` in **info mode** may return a fallback error message if the LLM call fails.
- **Booking flow** still works end-to-end (collect -> admin approve -> record), because it is mostly deterministic.

Mitigation (temporary):
- Set `LLM_PROVIDER=echo` and `EMBEDDINGS_PROVIDER=fake` to run without any LLM API dependency.
- Keep booking enabled; info answers will be deterministic.

Evidence to collect:
- Timestamp (UTC), request id (if available), and full error message from logs.
- Provider and model:
  - `LLM_PROVIDER`, `LLM_MODEL`
  - `EMBEDDINGS_PROVIDER`, `EMBEDDINGS_MODEL`

### B) Azure regional capacity / subscription limits

Symptoms:
- Deployment fails creating resources (Container Apps env, Function App plan, ACR, etc).
- Errors mentioning “quota”, “capacity”, “not allowed”, “limit”.

Evidence to collect:
- Failed deployment operation output:
  - `az deployment group show ...`
  - `az deployment group operation list ...`

## 3) CLI Diagnostics (Optional)

List resource groups:

```bash
az group list -o table
```

Inventory a specific RG:

```bash
bash scripts/azure/inventory.sh <rg>
```

## 4) Support Ticket Payload Template (Copy/Paste)

Use this to file an Azure support request (quota/capacity increase).

**Title**
- Quota increase request for Parking Chatbot demo deployment

**Subscription**
- `<subscription-id>`

**Region**
- `<region>` (example: `eastus`)

**Resource provider / type**
- `<resource-type>` (examples: Azure OpenAI, Container Apps, Functions, Cosmos DB)

**Current limit / requested limit**
- Current: `<current>`
- Requested: `<requested>`

**Business justification**
- This is a portfolio/demo application used for reviewer validation and technical interviews.
- The environment runs a small UI/API (Container Apps) + Durable Functions workflow with Cosmos persistence.
- We need stable capacity to run end-to-end booking + admin approval + recording during reviews.

**Architecture summary**
- UI/API: Azure Container App `chatbot-parking-ui`
- Durable: Function App `chatbot-parking-func`
- Persistence: Cosmos DB (SQL API), accessed via Managed Identity (Cosmos RBAC)

**Evidence**
- Error message(s) copied from Azure deployment output or runtime logs
- Timestamp(s) and correlation id(s) if available

