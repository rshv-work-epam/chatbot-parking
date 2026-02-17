# Guardrails Summary

## Sensitive Data Detection Rules

The demo applies regex-based redaction and filtering for:

- credit card-like sequences
- SSN-like numbers
- passport-like IDs
- phone numbers
- email addresses
- password keywords
- common secrets/tokens (best-effort): OpenAI/Google keys, AWS keys, GitHub/Slack tokens, private keys, JWT-like tokens

See `chatbot_parking.guardrails` for the exact patterns.

## Guardrail Layers

1. **Ingestion redaction**: documents are redacted before ingestion and tagged as `public`/`private`.
2. **Retrieval filtering**: chunks marked `private` are filtered out of results.
3. **Output filter**: responses are blocked if they contain sensitive patterns.

## OWASP LLM Top 10 (2025) Alignment (High-Level)

This repo is a small demo, but it implements defense-in-depth that maps to the OWASP LLM Top 10 (2025):

- **LLM01 Prompt Injection**: prompt templates treat retrieved context as untrusted; prompt-injection patterns in retrieved chunks are filtered; obvious injection attempts are refused.
- **LLM02 Sensitive Information Disclosure**: ingestion redaction + retrieval filtering + output blocking for sensitive patterns (PII + common secrets).
- **LLM03 Supply Chain**: use dependency hygiene (pin/scan) in deployment pipelines (recommended; not enforced by default in this repo).
- **LLM04 Data and Model Poisoning**: static KB ingestion is redacted; retrieved chunks that look like prompt-injection are excluded (helps reduce poisoned-context influence).
- **LLM05 Improper Output Handling**: UIs render untrusted values using safe DOM APIs (avoid `innerHTML` with untrusted data); backend never executes model output.
- **LLM06 Excessive Agency**: side effects (booking record) require explicit user confirmation + human admin approval; LLM output is not used as authority for actions.
- **LLM07 System Prompt Leakage**: system prompt contains no secrets; requests for internal prompts/instructions are refused.
- **LLM08 Vector and Embedding Weaknesses**: retrieval filters out sensitive and injection-like chunks; optional source IDs can be attached to answers for traceability.
- **LLM09 Misinformation**: prompting instructs the model to answer only from provided context/dynamic info and say “I don’t know” otherwise; optional sources reduce overreliance.
- **LLM10 Unbounded Consumption**: message length and context/output length limits can be enforced via env vars.

## Configuration Knobs

- `MAX_MESSAGE_CHARS` (default `2000`): reject overly large inbound messages in the API and chatbot.
- `MAX_THREAD_ID_CHARS` (default `128`): reject overly large thread IDs.
- `MAX_RAG_CONTEXT_CHARS` (default `6000`): truncate RAG context passed into the model.
- `MAX_RESPONSE_CHARS` (default `4000`): truncate assistant responses.
- `RAG_INCLUDE_SOURCES=true`: append `Sources: ...` using retrieved document IDs.
- `GUARDRAILS_USE_ML=true|false`: enable/disable optional NER-based sensitive-data detection.

## Example Block

If a user asks for private contact details, the response is replaced with:

> "Sorry, I cannot share private information."
