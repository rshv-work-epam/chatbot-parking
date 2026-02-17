"""FastAPI server exposing prompt UI and admin UI for local and cloud usage."""

from __future__ import annotations

from pathlib import Path
import os
import time
from typing import Optional
from urllib import request
from uuid import uuid4
import json

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from chatbot_parking.admin_store import (
    create_admin_request,
    get_admin_decision,
    get_admin_request,
    list_pending_requests,
    post_admin_decision,
)
from chatbot_parking.chatbot import ParkingChatbot
from chatbot_parking.cli import is_reservation_intent
from chatbot_parking.interactive_flow import run_chat_turn
from chatbot_parking.persistence import get_persistence

app = FastAPI(title="Parking Chat + Admin UI")
chatbot = ParkingChatbot()


def _resolve_ui_dir() -> Path:
    env_dir = os.getenv("UI_DIR")
    candidates: list[Path] = []
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.extend(
        [
            Path("/app/scripts"),
            Path(__file__).resolve().parents[2] / "scripts",
            Path(__file__).resolve().parents[3] / "scripts",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


UI_DIR = _resolve_ui_dir()


def _build_admin_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    function_key = os.getenv("DURABLE_FUNCTION_KEY")
    if function_key:
        headers["x-functions-key"] = function_key
    return headers


def _post_json(url: str, payload: dict) -> dict:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_build_admin_headers(),
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str) -> dict:
    req = request.Request(url, headers=_build_admin_headers(), method="GET")
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _invoke_durable_chat(message: str, thread_id: str) -> dict:
    base_url = os.getenv("DURABLE_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("DURABLE_BASE_URL is not configured")

    start_url = f"{base_url}/api/chat/start"
    starter = _post_json(start_url, {"message": message, "thread_id": thread_id})

    status_url = starter.get("statusQueryGetUri")
    if not status_url:
        raise RuntimeError("Durable starter response did not include statusQueryGetUri")

    timeout_seconds = float(os.getenv("DURABLE_POLL_TIMEOUT", "20"))
    poll_interval = float(os.getenv("DURABLE_POLL_INTERVAL", "1.0"))
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        status = _get_json(status_url)
        runtime_status = status.get("runtimeStatus")

        if runtime_status == "Completed":
            output = status.get("output") or {}
            if not isinstance(output, dict):
                raise RuntimeError("Durable output is not a JSON object")
            return output

        if runtime_status in {"Failed", "Terminated", "Canceled"}:
            raise RuntimeError(f"Durable orchestration ended with status: {runtime_status}")

        time.sleep(poll_interval)

    raise RuntimeError("Timed out waiting for Durable orchestration result")


def _require_admin_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("ADMIN_UI_TOKEN")
    if expected and x_api_token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")


class RequestIn(BaseModel):
    name: str
    surname: str
    car_number: str
    reservation_period: str


class DecisionIn(BaseModel):
    request_id: str
    approved: bool
    notes: Optional[str] = None


class ChatPromptIn(BaseModel):
    message: str


class ChatMessageIn(BaseModel):
    message: str
    thread_id: Optional[str] = None


@app.get("/admin/health")
def admin_health() -> dict:
    return {"status": "ok", "service": "ui_admin_api"}


@app.post("/chat/ask")
def ask_chatbot(payload: ChatPromptIn):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if is_reservation_intent(message):
        return {
            "response": (
                "Reservation request detected. Please use the admin request API "
                "or interactive booking flow to collect user booking details."
            )
        }

    return {"response": chatbot.answer_question(message)}


@app.post("/chat/message")
def chat_message(payload: ChatMessageIn):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    thread_id = payload.thread_id or str(uuid4())

    # Prefer durable cloud execution when configured.
    if os.getenv("DURABLE_BASE_URL"):
        try:
            result = _invoke_durable_chat(message=message, thread_id=thread_id)
            result.setdefault("thread_id", thread_id)
            result.setdefault("mode", "info")
            return result
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Durable backend error: {exc}") from exc

    persistence = get_persistence()
    prior_state = persistence.get_thread(thread_id)
    result, next_state = run_chat_turn(
        message=message,
        state=prior_state,
        persistence=persistence,
        answer_question=chatbot.answer_question,
    )
    persistence.upsert_thread(thread_id, next_state)

    response: dict[str, object] = {
        **result,
        "thread_id": thread_id,
    }
    response.setdefault("response", "")
    response.setdefault("mode", "info")
    response.setdefault("status", "collecting")
    return response


@app.get("/chat/status/{thread_id}")
def chat_status(thread_id: str):
    state = get_persistence().get_thread(thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="Thread not found")
    return state


@app.get("/chat/ui")
def chat_ui():
    ui_path = UI_DIR / "chat_ui.html"
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(ui_path, media_type="text/html")


@app.post("/admin/request")
def create_request(payload: RequestIn, _auth: None = Depends(_require_admin_token)):
    request_id = create_admin_request(payload.model_dump())
    return {"request_id": request_id}


@app.get("/admin/requests")
def list_requests(_auth: None = Depends(_require_admin_token)):
    return list_pending_requests()


@app.get("/admin/decisions/{request_id}")
def get_decision(request_id: str, _auth: None = Depends(_require_admin_token)):
    request_item = get_admin_request(request_id)
    if not request_item:
        raise HTTPException(status_code=404, detail="Not found")

    decision = get_admin_decision(request_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision pending")
    return decision


@app.post("/admin/decision")
def post_decision(decision: DecisionIn, _auth: None = Depends(_require_admin_token)):
    decision_result = post_admin_decision(
        request_id=decision.request_id,
        approved=decision.approved,
        notes=decision.notes,
    )
    if not decision_result:
        raise HTTPException(status_code=404, detail="Request not found")
    return decision_result


@app.get("/admin/ui")
def admin_ui():
    ui_path = UI_DIR / "admin_ui.html"
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(ui_path, media_type="text/html")


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/chat/ui", status_code=307)
