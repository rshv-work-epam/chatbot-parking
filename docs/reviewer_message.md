# Reviewer Message (Template)

Use this message when submitting the updated implementation for review.

---

Hi!

I addressed the review feedback and updated the implementation to be “reviewer-ready”:

## What Was Fixed / Improved

- **Stage 1**
  - Added **document chunking** in RAG ingestion/retrieval (`src/chatbot_parking/rag.py`).
  - Strengthened **guardrails** beyond regex-only with an **optional ML/NER detector** (Transformers NER pipeline) in `src/chatbot_parking/guardrails.py` (configurable via `GUARDRAILS_USE_ML`, `GUARDRAILS_NER_MODEL`).
  - Improved intent routing by supporting LLM-based intent classification (with deterministic fallback when running in echo mode).

- **Stage 2**
  - Admin approval is served via a unified FastAPI UI/API app (`src/chatbot_parking/web_demo_server.py`) with token protection (`x-api-token`).
  - Booking validation was improved (car number + reservation period) and UX includes a **review/confirm** step before submission.

- **Stage 3**
  - Reservation recording is done via a **real MCP tool server using stdio transport**:
    - MCP server: `src/chatbot_parking/mcp_servers/reservations_stdio_server.py`
    - MCP tool: `src/chatbot_parking/mcp_servers/reservations_server.py`
    - MCP client: `src/chatbot_parking/mcp_client.py`
  - No direct Python import/call bypasses the MCP protocol.

- **Stage 4**
  - Added **end-to-end tests** that cover booking -> admin approval -> reservation recording.
  - Added a minimal **load test** script for the chat API (`scripts/load_test_chat_message.py`).

## Live Demo URLs (Azure)

- Prompt UI (Chat): `<CHAT_UI_URL>`
- Admin UI: `<ADMIN_UI_URL>`
- Version stamp: `<VERSION_URL>` (returns `git_sha` + build time; also shown in the UI header)

Current deployment (example):
- Chat UI: `https://chatbot-parking-ui.salmoncliff-0defb751.eastus.azurecontainerapps.io/chat/ui`
- Admin UI: `https://chatbot-parking-ui.salmoncliff-0defb751.eastus.azurecontainerapps.io/admin/ui`
- Version: `https://chatbot-parking-ui.salmoncliff-0defb751.eastus.azurecontainerapps.io/version`

## How To Test (2-3 minutes)

1. Open Chat UI and start a booking: “I want to reserve a spot”.
2. Provide details (name, surname, car number, reservation period).
3. Type `confirm` to submit for admin approval.
4. Open Admin UI and enter the admin token (`x-api-token`).
5. Approve the pending request.
6. Return to Chat UI and send `status` (or any message). Expect “Confirmed and recorded.”

## Admin Token

Admin UI uses `x-api-token`. Provide this token out-of-band, or retrieve it from Azure (do not paste into chat):

```bash
az containerapp secret list -g rg-chatbot-parking-v2 -n chatbot-parking-ui --show-values \
  --query "[?name=='admin-ui-token'].value" -o tsv
```

Thanks!

