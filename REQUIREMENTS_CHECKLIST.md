# AI Engineering Fast Track Course - Requirements Checklist (Reviewer-Ready)

This file maps course requirements to the **current** repo implementation (local + Azure hybrid deployment).

## ✅ STAGE 1: Creation of a RAG System and Chatbot

### RAG architecture + vector DB
- ✅ `src/chatbot_parking/rag.py`
  - Chunking implemented via `RecursiveCharacterTextSplitter` / `TokenTextSplitter`.
  - Vector backends: FAISS (demo) and Weaviate (optional).
  - Embeddings providers: Fake, HuggingFace, OpenAI.

### Interactive features (info + booking)
- ✅ `src/chatbot_parking/interactive_flow.py`
  - Info Q&A mode: RAG answers + dynamic data (availability/hours/pricing).
  - Booking mode: slot filling + validation + review/confirm step.
  - Supports free-form “structured-ish” input (e.g. `name: John; car: AA-1234; period: ...`) via `src/chatbot_parking/booking_utils.py`.

### Guardrails (beyond regex-only)
- ✅ `src/chatbot_parking/guardrails.py`
  - Regex detection for common PII/secrets.
  - Optional ML/NER detection using a pre-trained NER model (Transformers pipeline) when `GUARDRAILS_USE_ML=true`.
  - Applied at ingestion (redaction), retrieval (private chunk filtering), and output (block/redact).
  - Docs: `docs/guardrails.md`.

### Evaluation
- ✅ `src/chatbot_parking/eval/evaluate.py`
  - Recall@K / Precision@K + latency p50/p95.
  - Reports written to `eval/results/` and summarized in `docs/evaluation_report.md`.

## ✅ STAGE 2: Human-in-the-Loop Agent

- ✅ Admin approvals API + UI served from a single FastAPI app:
  - `src/chatbot_parking/web_demo_server.py` serves:
    - Prompt UI: `GET /chat/ui`
    - Admin UI: `GET /admin/ui`
    - Admin API: `GET /admin/requests`, `POST /admin/decision` (token-protected via `x-api-token`)
- ✅ Persistence-backed approvals (no in-memory loss in cloud):
  - `src/chatbot_parking/persistence.py` supports Cosmos DB (cloud) or in-memory (local/dev).

## ✅ STAGE 3: Reservation Recording via MCP Server (Real Protocol)

- ✅ Real MCP stdio tool server:
  - Tool: `src/chatbot_parking/mcp_servers/reservations_server.py`
  - Stdio entrypoint: `src/chatbot_parking/mcp_servers/reservations_stdio_server.py`
- ✅ Real MCP client (stdio transport) used by the booking flow:
  - `src/chatbot_parking/mcp_client.py`
- ✅ Record format:
  - `Name | Car Number | Reservation Period | Approval Time`

## ✅ STAGE 4: Orchestration via LangGraph + Testing

- ✅ LangGraph orchestration:
  - `src/chatbot_parking/orchestration.py`
- ✅ End-to-end tests:
  - Local E2E booking + admin approval + recording: `tests/test_web_demo_server_e2e.py`
  - Booking flow validation and review UX: `tests/test_e2e_booking_flow.py`, `tests/test_interactive_flow_validation.py`
- ✅ Load/system testing:
  - Minimal load test script (no extra deps): `scripts/load_test_chat_message.py`

## ✅ Azure Hybrid Deployment (Production-Oriented Demo)

This repo includes a hybrid Azure runtime aligned with “portfolio production” best practices:

- UI/API: Azure Container Apps (`chatbot-parking-ui`) serving `/chat/ui`, `/admin/ui`, and APIs.
- Orchestration: Azure Durable Functions for booking turns.
- Persistence: Cosmos DB (SQL API) for threads + approvals + reservations, using **Managed Identity**.
- Cost guardrails: `$10` budget + best-effort “kill switch” endpoint.

Docs:
- Runbook: `docs/devops_production_azure_github.md`
- Quota troubleshooting template: `docs/quota_support_payload.md`

### Ready for Review
All code is on the main branch and tested. The project meets all specified requirements with additional enhancements.
