"""Azure Durable Functions entrypoint for cloud chat orchestration."""

from __future__ import annotations

import os
import json
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

import azure.durable_functions as df
import azure.functions as func
from azure.identity import DefaultAzureCredential
import requests

# Allow importing project source when this function app is deployed from repository content.
# In Azure Functions, `function_app.py` lives at the app root (wwwroot), so `./src` is the
# expected location once the deployment package copies the repository `src/` directory.
SRC_PATH = Path(__file__).resolve().parent / "src"
if not SRC_PATH.exists():
    # Fallback for local execution from the repository checkout layout.
    SRC_PATH = Path(__file__).resolve().parents[3] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from chatbot_parking.interactive_flow import run_chat_turn
from chatbot_parking.persistence import get_persistence

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)

ARM_SCOPE = "https://management.azure.com/.default"


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _arm_post(url: str, *, token: str) -> dict[str, Any]:
    # ARM stop/start operations are async; 202/204 is normal.
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    ok = 200 <= resp.status_code < 300
    payload: dict[str, Any] = {
        "ok": ok,
        "status_code": resp.status_code,
    }
    if resp.text:
        # Avoid raising on non-JSON bodies (ARM sometimes returns empty or HTML-ish error text).
        try:
            payload["body"] = resp.json()
        except Exception:
            payload["body"] = resp.text[:2000]
    return payload


@app.route(route="budget/stop", methods=["POST", "GET"])
def budget_stop(req: func.HttpRequest) -> func.HttpResponse:
    """
    Budget-triggered kill switch.

    Intended to be called from an Azure Cost Management Budget via an Action Group webhook receiver.

    Notes:
    - This is not a true “hard cap”: budget evaluation and cost data can lag, so treat this as best-effort.
    - Some Azure resources continue billing even when “apps” are stopped (e.g., ACR, Storage capacity).
    """
    try:
        subscription_id = _env("AUTO_STOP_SUBSCRIPTION_ID")
        resource_group = _env("AUTO_STOP_RESOURCE_GROUP")
        container_apps_raw = os.environ.get("AUTO_STOP_CONTAINER_APP_NAMES", "").strip()
        function_app_name = os.environ.get("AUTO_STOP_FUNCTION_APP_NAME", "").strip()
        stop_self = os.environ.get("AUTO_STOP_STOP_FUNCTION_APP", "false").strip().lower() in {"1", "true", "yes"}

        container_apps = [x.strip() for x in container_apps_raw.split(",") if x.strip()]
        if not container_apps and not (stop_self and function_app_name):
            return func.HttpResponse(
                "No targets configured. Set AUTO_STOP_CONTAINER_APP_NAMES and/or AUTO_STOP_STOP_FUNCTION_APP.",
                status_code=400,
            )

        ca_api_version = os.environ.get("AUTO_STOP_CONTAINERAPPS_API_VERSION", "2024-03-01").strip()
        web_api_version = os.environ.get("AUTO_STOP_WEB_API_VERSION", "2024-04-01").strip()

        cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        token = cred.get_token(ARM_SCOPE).token

        results: dict[str, Any] = {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "stopped": {
                "container_apps": {},
                "function_app": None,
            },
        }

        for name in container_apps:
            url = (
                "https://management.azure.com"
                f"/subscriptions/{subscription_id}"
                f"/resourceGroups/{resource_group}"
                f"/providers/Microsoft.App/containerApps/{name}"
                f"/stop?api-version={ca_api_version}"
            )
            results["stopped"]["container_apps"][name] = _arm_post(url, token=token)

        if stop_self:
            if not function_app_name:
                return func.HttpResponse("AUTO_STOP_FUNCTION_APP_NAME must be set when AUTO_STOP_STOP_FUNCTION_APP=true", status_code=400)
            url = (
                "https://management.azure.com"
                f"/subscriptions/{subscription_id}"
                f"/resourceGroups/{resource_group}"
                f"/providers/Microsoft.Web/sites/{function_app_name}"
                f"/stop?api-version={web_api_version}"
            )
            results["stopped"]["function_app"] = _arm_post(url, token=token)

        return func.HttpResponse(
            body=json.dumps(results, ensure_ascii=True, sort_keys=True),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as e:
        return func.HttpResponse(f"budget_stop failed: {e}", status_code=500)


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

    def _durable_answer_question(_text: str) -> str:
        # The Durable backend is intended to orchestrate booking + approval reliably.
        # Keep dependencies minimal (avoid RAG/embeddings installs in the Functions build).
        return "Info questions are handled by the UI service. Start a booking to continue."

    persistence = get_persistence()

    prior_state = persistence.get_thread(thread_id)
    result, next_state = run_chat_turn(
        message=message,
        state=prior_state,
        persistence=persistence,
        answer_question=_durable_answer_question,
    )
    persistence.upsert_thread(thread_id, next_state)

    response = {
        **result,
        "thread_id": thread_id,
    }
    response.setdefault("response", "")
    response.setdefault("mode", "info")
    response.setdefault("status", "collecting")
    return response
