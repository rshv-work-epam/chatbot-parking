# Guardrails Summary

## Sensitive Data Detection Rules

The demo applies **regex-based detection** plus an **optional ML/NER pass** (pre-trained NER model via Transformers)
to reduce the chance of leaking sensitive data.

Regex detection covers:

- credit card-like sequences
- SSN-like numbers
- passport-like IDs
- phone numbers
- email addresses
- password keywords
- common secrets/tokens (best-effort): OpenAI/Google keys, AWS keys, GitHub/Slack tokens, private keys, JWT-like tokens

Optional ML/NER detection:

- Enabled by default in **dev/local** when the dependency is available, and **disabled by default in prod**
  to avoid cold-start model downloads (`GUARDRAILS_USE_ML=true|false`).
- Configurable model name via `GUARDRAILS_NER_MODEL` (default: `dslim/bert-base-NER`).

See `src/chatbot_parking/guardrails.py` for the exact patterns and ML settings.

## Guardrail Layers

1. **Ingestion redaction**: documents are redacted before ingestion and tagged as `public`/`private`.
2. **Retrieval filtering**: chunks marked `private` are filtered out of results.
3. **Output filter**: responses are blocked if they contain sensitive patterns.
4. **HTTP safety**: rate limiting + security headers are enforced in the UI/API service.
   - In `APP_ENV=prod`, API docs are not exposed (`/docs`, `/redoc`, `/openapi.json` return 404).
   - Trusted host allow-list is enabled in prod (`ALLOWED_HOSTS`).
   - Slack and WhatsApp webhooks support signature verification + anti-replay controls.
5. **Tool safety**: reservation tool inputs are sanitized before writing to file.

## OWASP LLM Top 10 (2025) Alignment (High-Level)

This repo is a small demo, but it implements defense-in-depth that maps to the OWASP LLM Top 10 (2025):

- **LLM01 Prompt Injection**: prompt templates treat retrieved context as untrusted; prompt-injection patterns in retrieved chunks are filtered; obvious injection attempts are refused. (`src/chatbot_parking/guardrails.py`, `src/chatbot_parking/rag.py`)
- **LLM02 Sensitive Information Disclosure**: ingestion redaction + retrieval filtering + output blocking for sensitive patterns (PII + common secrets). (`src/chatbot_parking/guardrails.py`, `src/chatbot_parking/rag.py`)
- **LLM03 Supply Chain**: deployment uses GitHub OIDC (no long-lived Azure credentials) and secrets are stored in Azure Container Apps secrets; add SCA/vuln scanning in CI for real prod. (`.github/workflows/ci.yml`, `.github/workflows/cd-azure-containerapps.yml`)
- **LLM04 Data and Model Poisoning**: ingestion redacts PII and retrieval filters injection-like chunks to reduce poisoned-context influence. (`src/chatbot_parking/rag.py`)
- **LLM05 Improper Output Handling**: UIs render untrusted values using safe DOM APIs (no `innerHTML`); backend never executes model output. (`scripts/chat_ui.html`, `scripts/admin_ui.html`)
- **LLM06 Excessive Agency**: side effects (reservation record) require explicit user confirmation + human admin approval; tool calls are initiated by application code, not model output. (`src/chatbot_parking/interactive_flow.py`)
- **LLM07 System Prompt Leakage**: system prompt contains no secrets; requests for internal prompts/instructions are refused. (`src/chatbot_parking/guardrails.py`, `src/chatbot_parking/rag.py`)
- **LLM08 Vector and Embedding Weaknesses**: chunking + metadata tagging; retrieval filters out private and injection-like chunks; optional sources for traceability. (`src/chatbot_parking/rag.py`)
- **LLM09 Misinformation**: prompting instructs the model to answer only from provided context/dynamic info and say “I don’t know” otherwise; optional sources reduce overreliance. (`src/chatbot_parking/rag.py`)
- **LLM10 Unbounded Consumption**: message length/context/output length limits + request rate limiting. (`src/chatbot_parking/web_demo_server.py`, `src/chatbot_parking/http_security.py`)

Note: OWASP also published an earlier “Top 10 for LLM Applications” list (2023/2024) with different numbering. The mitigations above still apply; only category labels changed.

## Configuration Knobs

- `MAX_MESSAGE_CHARS` (default `2000`): reject overly large inbound messages in the API and chatbot.
- `MAX_THREAD_ID_CHARS` (default `128`): reject overly large thread IDs.
- `MAX_RAG_CONTEXT_CHARS` (default `6000`): truncate RAG context passed into the model.
- `MAX_RESPONSE_CHARS` (default `4000`): truncate assistant responses.
- `RAG_INCLUDE_SOURCES=true`: append `Sources: ...` using retrieved document IDs.
- `GUARDRAILS_USE_ML=true|false`: enable/disable optional NER-based sensitive-data detection.
- `RATE_LIMIT_ENABLED=true|false`: enable request rate limiting (defaults to enabled in `APP_ENV=prod`).
- `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`: tune rate limiting (defaults: 60 requests per 60 seconds).
- `COSMOS_USE_MANAGED_IDENTITY=true`: use Azure Managed Identity instead of Cosmos keys (requires Cosmos RBAC setup).

## Example Block

If a user asks for private contact details, the response is replaced with:

> "Sorry, I cannot share private information."
