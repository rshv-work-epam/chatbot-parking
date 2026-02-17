"""Azure Durable Functions entrypoint for cloud chat orchestration."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

import azure.durable_functions as df
import azure.functions as func

# Allow importing project source when this function app is deployed from repository content.
SRC_PATH = Path(__file__).resolve().parents[3] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from chatbot_parking.chatbot import ParkingChatbot
from chatbot_parking.interactive_flow import run_chat_turn
from chatbot_parking.persistence import get_persistence

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="chat/start")
@app.durable_client_input(client_name="client")
async def start_chat_orchestration(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    """Start a durable workflow for one chat turn and return status URLs."""
    try:
        payload = req.get_json()
    except ValueError:
        payload = {}

    message = str(payload.get("message", "")).strip()
    thread_id = str(payload.get("thread_id", "")).strip() or str(uuid4())

    instance_id = await client.start_new(
        "chat_orchestrator",
        None,
        {
            "message": message,
            "thread_id": thread_id,
        },
    )
    return client.create_check_status_response(req, instance_id)


@app.orchestration_trigger(context_name="context")
def chat_orchestrator(context: df.DurableOrchestrationContext):
    payload = context.get_input() or {}
    result = yield context.call_activity("run_chat_turn_activity", payload)
    return result


@app.activity_trigger(input_name="payload")
def run_chat_turn_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Run a single chat turn with persistent state."""
    message = str(payload.get("message", "")).strip()
    thread_id = str(payload.get("thread_id", "")).strip() or str(uuid4())

    if not message:
        return {
            "response": "Message cannot be empty",
            "thread_id": thread_id,
            "mode": "info",
            "status": "collecting",
        }

    persistence = get_persistence()
    chatbot = ParkingChatbot()

    prior_state = persistence.get_thread(thread_id)
    result, next_state = run_chat_turn(
        message=message,
        state=prior_state,
        persistence=persistence,
        answer_question=chatbot.answer_question,
    )
    persistence.upsert_thread(thread_id, next_state)

    response = {
        "response": result.get("response", ""),
        "thread_id": thread_id,
        "mode": result.get("mode", "info"),
        "status": result.get("status", "collecting"),
    }
    if result.get("request_id") is not None:
        response["request_id"] = result["request_id"]
    return response
