# Chatbot Parking Reservation

This project provides a reference implementation of a parking reservation chatbot using LangChain + LangGraph with a RAG-based architecture. The solution includes:

- A RAG-powered chatbot for information retrieval and reservation intake.
- A human-in-the-loop admin agent stub.
- A FastAPI MCP-style server that records approved reservations.
- A LangGraph orchestration pipeline that wires the workflow.

## Quick Start (Demo Mode)

Demo mode uses FAISS + FakeEmbeddings + EchoLLM (default).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m chatbot_parking.main
```

## Ingest Static Documents (Demo/Real)

```bash
python data/ingest.py
```

## Running the Admin API

```bash
export ADMIN_API_TOKEN=change-me
uvicorn chatbot_parking.admin_api:app --reload
```

Set `ADMIN_API_URL=http://localhost:8000` to submit booking requests.
Use `ADMIN_AUTO_APPROVE=true|false` to toggle auto-approval. When disabled, post a decision via
`POST /admin/decision` or inspect pending requests via `GET /admin/requests`.
Requests require `x-api-token: $ADMIN_API_TOKEN`.

## Running the MCP Server

```bash
uvicorn chatbot_parking.mcp_server:app --reload
```

Use the `/record` endpoint with the `x-api-token: change-me` header to store approved reservations in `data/reservations.txt`.
Set `MCP_SERVER_URL=http://localhost:8001` and `MCP_API_TOKEN=change-me` to enable HTTP recording.

## Docker Compose (Admin + MCP + Weaviate)

```bash
docker compose up --build
```

## Real Mode (Weaviate + HuggingFace embeddings + OpenAI LLM)

```bash
docker compose up -d weaviate
export VECTOR_BACKEND=weaviate
export WEAVIATE_URL=http://localhost:8080
export EMBEDDINGS_PROVIDER=hf
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your-key
python data/ingest.py
python -m chatbot_parking.main
```

## Evaluation

```bash
python -m chatbot_parking.eval.evaluate --write-report
```

Results are saved in `eval/results/` and `docs/evaluation_report.md` is updated.

## Project Layout

- `src/chatbot_parking/chatbot.py`: Core chatbot logic and reservation intake.
- `src/chatbot_parking/rag.py`: Vector store setup and retrieval.
- `src/chatbot_parking/admin_agent.py`: Human-in-the-loop approval stub.
- `src/chatbot_parking/admin_api.py`: Admin REST API for approve/deny actions.
- `src/chatbot_parking/mcp_server.py`: Reservation recording server.
- `src/chatbot_parking/mcp_client.py`: Client for recording reservations via MCP.
- `src/chatbot_parking/orchestration.py`: LangGraph workflow.
- `data/static_docs.json`: Static documents for RAG ingestion.
- `data/ingest.py`: Ingestion script for guardrails + reporting.
- `docs/guardrails.md`: Guardrails summary and examples.

See `docs/evaluation.md` for guidance and `docs/evaluation_report.md` for the latest metrics report.

## Example Dialogue Flow

- User: "What are the working hours?"
- Assistant: returns hours + pricing + availability.
- User: "I want to book a spot."
- Assistant: collects name → surname → car number → reservation period.
- Admin: approves via `/admin/decision`.
- Assistant: records to `data/reservations.txt` (via MCP server when configured).

## Docs References

- LangChain Weaviate integration: https://python.langchain.com/docs/integrations/vectorstores/weaviate/
- LangChain embeddings: https://python.langchain.com/docs/integrations/text_embedding/
- LangChain chat models: https://python.langchain.com/docs/integrations/chat/
- Weaviate Docker deployment: https://weaviate.io/developers/weaviate/installation/docker-compose
- FastAPI dependencies & headers: https://fastapi.tiangolo.com/tutorial/dependencies/
- OpenAI API docs: https://platform.openai.com/docs
- Azure OpenAI docs: https://learn.microsoft.com/azure/ai-services/openai/

## Tests

```bash
pytest
```
