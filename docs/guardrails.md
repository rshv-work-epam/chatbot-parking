# Guardrails Summary

## PII Detection Rules

The demo applies regex-based redaction and filtering for:

- credit card-like sequences
- SSN-like numbers
- passport-like IDs
- phone numbers
- email addresses
- password keywords

See `chatbot_parking.guardrails` for the exact patterns.

## Guardrail Layers

1. **Ingestion redaction**: documents are redacted before ingestion and tagged as `public`/`private`.
2. **Retrieval filtering**: chunks marked `private` are filtered out of results.
3. **Output filter**: responses are blocked if they contain sensitive patterns.

## Example Block

If a user asks for private contact details, the response is replaced with:

> "Sorry, I cannot share private information."
