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
python -m chatbot_parking.main
```

## Running the MCP Server

```bash
uvicorn chatbot_parking.mcp_server:app --reload
```

Use the `/record` endpoint with the `x-api-token: change-me` header to store approved reservations in `data/reservations.txt`.

## Running the Admin API

```bash
uvicorn chatbot_parking.admin_server:app --reload
```

Use `/admin/request` to submit requests and `/admin/decision` to approve/deny them. Both endpoints require the `x-api-token: change-me` header.

## Configuration

The workflow uses environment variables for external integrations:

- `ADMIN_ENDPOINT`: REST endpoint for admin approval requests (optional).
- `ADMIN_API_TOKEN`: Token passed as `x-api-token` to the admin endpoint.
- `MCP_ENDPOINT`: MCP server `/record` endpoint (e.g., `http://localhost:8000/record`).
- `MCP_API_TOKEN`: Token for MCP server authorization.

If `ADMIN_ENDPOINT` is not set, the admin agent auto-approves requests. If `MCP_ENDPOINT` is not set, approved reservations are not recorded externally.

## Project Layout

- `src/chatbot_parking/chatbot.py`: Core chatbot logic and reservation intake.
- `src/chatbot_parking/rag.py`: Vector store setup and retrieval.
- `src/chatbot_parking/admin_agent.py`: Human-in-the-loop approval stub.
- `src/chatbot_parking/mcp_server.py`: Reservation recording server.
- `src/chatbot_parking/mcp_client.py`: MCP server client for recording approvals.
- `src/chatbot_parking/orchestration.py`: LangGraph workflow.

## Evaluation

See `docs/evaluation.md` for sample metrics collection steps and reporting guidance.
