from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Optional
from uuid import uuid4
from datetime import datetime, timezone

app = FastAPI()


class RequestIn(BaseModel):
    name: str
    surname: str
    car_number: str
    reservation_period: str


class DecisionIn(BaseModel):
    request_id: str
    approved: bool
    notes: Optional[str] = None


STORE: Dict[str, Dict] = {}


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
    base = Path(__file__).resolve().parent
    ui_path = base / "admin_ui.html"
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(ui_path, media_type="text/html")


@app.get("/")
def root_redirect():
    """Redirect the root to the UI to make Codespaces links friendlier."""
    return RedirectResponse(url="/admin/ui", status_code=307)


if __name__ == "__main__":
    import uvicorn

    # Bind to 0.0.0.0 so port forwarding (e.g., Codespaces/Dev Containers) can reach it
    uvicorn.run(app, host="0.0.0.0", port=8000)
