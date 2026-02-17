"""Durable starter: starts one chat orchestration turn and returns status URLs."""

from __future__ import annotations

from uuid import uuid4

import azure.functions as func
import azure.durable_functions as df
import json


async def main(req: func.HttpRequest, starter: str) -> func.HttpResponse:
    client = df.DurableOrchestrationClient(starter)
    try:
        payload = req.get_json()
    except ValueError:
        payload = {}

    message = str(payload.get("message", "")).strip()
    thread_id = str(payload.get("thread_id", "")).strip() or str(uuid4())

    try:
        instance_id = await client.start_new(
            orchestration_function_name="chat_orchestrator",
            instance_id=None,
            client_input={"message": message, "thread_id": thread_id},
        )
    except Exception as exc:
        detail = f"{type(exc).__name__}: {str(exc)}"
        return func.HttpResponse(
            body=json.dumps({"error": "durable_start_failed", "detail": detail[:800]}),
            status_code=500,
            mimetype="application/json",
        )

    try:
        return client.create_check_status_response(req, instance_id)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {str(exc)}"
        return func.HttpResponse(
            body=json.dumps({"error": "durable_status_response_failed", "detail": detail[:800]}),
            status_code=500,
            mimetype="application/json",
        )
