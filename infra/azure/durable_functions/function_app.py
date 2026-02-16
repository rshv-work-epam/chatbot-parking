"""Azure Durable Functions entrypoint for cloud orchestration option."""

from __future__ import annotations

from typing import Any

import azure.durable_functions as df
import azure.functions as func

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="chat/start")
@app.durable_client_input(client_name="client")
async def start_chat_orchestration(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    """Start a durable workflow for a user prompt and return status URLs."""
    try:
        payload = req.get_json()
    except ValueError:
        payload = {}

    instance_id = await client.start_new("chat_orchestrator", None, payload)
    return client.create_check_status_response(req, instance_id)


@app.orchestration_trigger(context_name="context")
def chat_orchestrator(context: df.DurableOrchestrationContext):
    """Durable orchestrator coordinating prompt execution."""
    payload = context.get_input() or {}
    result = yield context.call_activity("run_prompt_activity", payload)
    return result


@app.activity_trigger(input_name="payload")
def run_prompt_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Activity that runs the chatbot prompt logic."""
    message = str(payload.get("message", "")).strip()
    if not message:
        return {"response": "Message cannot be empty"}

    try:
        from chatbot_parking.chatbot import ParkingChatbot

        chatbot = ParkingChatbot()
        response = chatbot.answer_question(message)
    except Exception as exc:  # pragma: no cover - cloud runtime fallback path
        response = f"Fallback response (runtime issue): {exc}"

    return {
        "message": message,
        "response": response,
    }
