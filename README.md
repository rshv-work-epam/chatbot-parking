# Chatbot Parking Reservation

This project provides a reference implementation of a parking reservation chatbot using LangChain + LangGraph with a RAG-based architecture. The solution includes:

- A RAG-powered chatbot for information retrieval and reservation intake.
- A human-in-the-loop admin agent stub.
- A FastAPI MCP-style server that records approved reservations.
- A LangGraph orchestration pipeline that wires the workflow.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m chatbot_parking.main
```

## Running the Admin API

```bash
uvicorn chatbot_parking.admin_api:app --reload
```

Set `ADMIN_API_URL=http://localhost:8000` to have the demo submit booking requests
to the admin API (auto-approved for the MVP client).

## Running the MCP Server

```bash
uvicorn chatbot_parking.mcp_server:app --reload
```

Use the `/record` endpoint with the `x-api-token: change-me` header to store approved reservations in `data/reservations.txt`.
Set `MCP_SERVER_URL=http://localhost:8001` and `MCP_API_TOKEN=change-me` to enable HTTP recording.

## Project Layout

- `src/chatbot_parking/chatbot.py`: Core chatbot logic and reservation intake.
- `src/chatbot_parking/rag.py`: Vector store setup and retrieval.
- `src/chatbot_parking/admin_agent.py`: Human-in-the-loop approval stub.
- `src/chatbot_parking/admin_api.py`: Admin REST API for approve/deny actions.
- `src/chatbot_parking/mcp_server.py`: Reservation recording server.
- `src/chatbot_parking/mcp_client.py`: Client for recording reservations via MCP.
- `src/chatbot_parking/orchestration.py`: LangGraph workflow.

## Evaluation

See `docs/evaluation.md` for sample metrics collection steps and reporting guidance.
Run `python -m chatbot_parking.eval.evaluate` to compute Recall@K/Precision@K on `eval/qa_dataset.json`.
