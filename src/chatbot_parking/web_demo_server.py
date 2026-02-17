"""Lightweight FastAPI server that exposes user and admin web UIs for demos."""

from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from chatbot_parking.chatbot import ParkingChatbot
from chatbot_parking.cli import is_reservation_intent
from chatbot_parking.admin_store import (
    STORE as ADMIN_STORE,
    create_admin_request,
    get_admin_decision,
    list_pending_requests,
    post_admin_decision,
)
from chatbot_parking.interactive_orchestration import DEFAULT_INTERACTIVE_GRAPH

app = FastAPI()
chatbot = ParkingChatbot()

UI_DIR = Path(__file__).resolve().parents[2] / "scripts"


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


STORE = ADMIN_STORE


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
    result = DEFAULT_INTERACTIVE_GRAPH.invoke(
        {"message": message},
        config={"configurable": {"thread_id": thread_id}},
    )

    response: dict[str, str] = {
        "response": result.get("response", ""),
        "thread_id": thread_id,
        "mode": result.get("mode", "info"),
    }
    if result.get("request_id") is not None:
        response["request_id"] = result["request_id"]
    if result.get("status") is not None:
        response["status"] = result["status"]
    return response


@app.get("/chat/ui")
def chat_ui():
    """Serve a small single-file web UI for user prompts."""
    ui_path = UI_DIR / "chat_ui.html"
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(ui_path, media_type="text/html")


@app.post("/admin/request")
def create_request(payload: RequestIn):
    request_id = create_admin_request(payload.model_dump())
    return {"request_id": request_id}


@app.get("/admin/requests")
def list_requests():
    """Return only pending requests (no decision yet)."""
    return list_pending_requests()


@app.get("/admin/decisions/{request_id}")
def get_decision(request_id: str):
    if request_id not in STORE:
        raise HTTPException(status_code=404, detail="Not found")
    decision = get_admin_decision(request_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision pending")
    return decision


@app.post("/admin/decision")
def post_decision(decision: DecisionIn):
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
    """Serve a small single-file web UI for manual approvals."""
    ui_path = UI_DIR / "admin_ui.html"
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(ui_path, media_type="text/html")


@app.get("/")
def root_redirect():
    """Redirect the root to the user chat UI for quick testing."""
    return RedirectResponse(url="/chat/ui", status_code=307)
