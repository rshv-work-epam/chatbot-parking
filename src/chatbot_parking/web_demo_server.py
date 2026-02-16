"""Lightweight FastAPI server that exposes user and admin web UIs for demos."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from chatbot_parking.chatbot import ParkingChatbot
from chatbot_parking.cli import is_reservation_intent

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


STORE: Dict[str, Dict[str, Any]] = {}


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


@app.get("/chat/ui")
def chat_ui():
    """Serve a small single-file web UI for user prompts."""
    ui_path = UI_DIR / "chat_ui.html"
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(ui_path, media_type="text/html")


@app.post("/admin/request")
def create_request(payload: RequestIn):
    request_id = str(uuid4())
    STORE[request_id] = {
        "request_id": request_id,
        "payload": payload.dict(),
        "decision": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"request_id": request_id}


@app.get("/admin/requests")
def list_requests():
    """Return only pending requests (no decision yet)."""
    return [v for v in STORE.values() if not v.get("decision")]


@app.get("/admin/decisions/{request_id}")
def get_decision(request_id: str):
    entry = STORE.get(request_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    if not entry["decision"]:
        raise HTTPException(status_code=404, detail="Decision pending")
    return entry["decision"]


@app.post("/admin/decision")
def post_decision(decision: DecisionIn):
    entry = STORE.get(decision.request_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Request not found")
    decided_at = datetime.now(timezone.utc).isoformat()
    entry["decision"] = {
        "approved": decision.approved,
        "decided_at": decided_at,
        "notes": decision.notes,
    }
    return entry["decision"]


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
