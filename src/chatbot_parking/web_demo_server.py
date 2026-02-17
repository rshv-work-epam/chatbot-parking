"""FastAPI server exposing prompt UI, admin UI, auth, and channel adapters."""

from __future__ import annotations

from pathlib import Path
import hmac
import hashlib
import os
import time
from typing import Any, Optional
from urllib import request
from uuid import uuid4
import json

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

try:
    from authlib.integrations.starlette_client import OAuth
except Exception:  # pragma: no cover - optional runtime dependency
    OAuth = None

from chatbot_parking.http_security import apply_security_headers, enforce_rate_limit
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

@app.middleware("http")
async def _security_headers_middleware(req: Request, call_next):
    resp = await call_next(req)
    apply_security_headers(req, resp)
    return resp

def _mcp_recording_enabled() -> bool:
    return os.getenv("MCP_RECORD_RESERVATIONS", "true").strip().lower() in {"1", "true", "yes", "on"}


def _record_reservation_via_mcp(
    *,
    name: str,
    car_number: str,
    reservation_period: str,
    approval_time: str | None = None,
) -> str:
    # Import lazily so environments that only use Durable Functions don't need MCP deps.
    from chatbot_parking.mcp_client import record_reservation

    return record_reservation(
        name=name,
        car_number=car_number,
        reservation_period=reservation_period,
        approval_time=approval_time,
    )


def _maybe_record_mcp_after_durable(thread_id: str, result: dict[str, Any]) -> None:
    if not _mcp_recording_enabled():
        return
    if result.get("mode") != "booking" or result.get("status") != "approved":
        return
    if result.get("mcp_recorded") is True:
        return

    collected = result.get("collected") if isinstance(result.get("collected"), dict) else {}
    name = f"{str(collected.get('name', '')).strip()} {str(collected.get('surname', '')).strip()}".strip()
    car_number = str(collected.get("car_number", "")).strip()
    reservation_period = str(collected.get("reservation_period", "")).strip()
    approval_time = str(result.get("decided_at") or "").strip() or None

    if not (name and car_number and reservation_period):
        return

    try:
        approval_time = _record_reservation_via_mcp(
            name=name,
            car_number=car_number,
            reservation_period=reservation_period,
            approval_time=approval_time,
        )
    except Exception as exc:
        detail = str(exc).strip() or "unknown error"
        result["status_detail"] = (
            f"{(result.get('status_detail') or '').strip()} "
            f"(MCP file record failed: {detail})"
        ).strip()
        return

    # Persist idempotency flag so a subsequent status check doesn't re-write the file.
    persistence = get_persistence()
    state = persistence.get_thread(thread_id) or {}
    state["mcp_recorded"] = True
    if approval_time:
        state["decided_at"] = state.get("decided_at") or approval_time
    persistence.upsert_thread(thread_id, state)
    result["mcp_recorded"] = True
    if approval_time and not result.get("decided_at"):
        result["decided_at"] = approval_time


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

SESSION_SECRET = os.getenv("SESSION_SECRET_KEY") or os.getenv("ADMIN_UI_TOKEN") or "dev-session-secret"
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").strip().lower() == "true"
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)

PROVIDER_TITLES: dict[str, str] = {
    "google": "Google",
    "github": "GitHub",
    "linkedin": "LinkedIn",
    "microsoft": "Microsoft",
    "apple": "Apple",
}

OAUTH_PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
    "google": {
        "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
        "client_kwargs": {"scope": "openid email profile"},
    },
    "microsoft": {
        "server_metadata_url": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
        "client_kwargs": {"scope": "openid profile email User.Read"},
    },
    "apple": {
        "server_metadata_url": "https://appleid.apple.com/.well-known/openid-configuration",
        "client_kwargs": {"scope": "name email"},
    },
    "github": {
        "api_base_url": "https://api.github.com/",
        "access_token_url": "https://github.com/login/oauth/access_token",
        "authorize_url": "https://github.com/login/oauth/authorize",
        "client_kwargs": {"scope": "read:user user:email"},
    },
    "linkedin": {
        "server_metadata_url": "https://www.linkedin.com/oauth/.well-known/openid-configuration",
        "client_kwargs": {"scope": "openid profile email"},
    },
}


def _init_oauth() -> tuple[Any, list[str]]:
    if OAuth is None:
        return None, []

    oauth = OAuth()
    enabled: list[str] = []
    for provider, config in OAUTH_PROVIDER_CONFIGS.items():
        client_id = os.getenv(f"OAUTH_{provider.upper()}_CLIENT_ID")
        client_secret = os.getenv(f"OAUTH_{provider.upper()}_CLIENT_SECRET")
        if not client_id or not client_secret:
            continue
        oauth.register(
            name=provider,
            client_id=client_id,
            client_secret=client_secret,
            **config,
        )
        enabled.append(provider)
    return oauth, enabled


oauth_client, enabled_oauth_providers = _init_oauth()

def _max_message_chars() -> int:
    return int(os.getenv("MAX_MESSAGE_CHARS", "2000"))


def _max_thread_id_chars() -> int:
    return int(os.getenv("MAX_THREAD_ID_CHARS", "128"))


def _enforce_text_limits(value: str, *, field: str) -> None:
    max_chars = _max_message_chars()
    if max_chars > 0 and len(value) > max_chars:
        raise HTTPException(
            status_code=413,
            detail=f"{field} is too long (max {max_chars} characters)",
        )


def _enforce_thread_id_limits(thread_id: str) -> None:
    max_chars = _max_thread_id_chars()
    if max_chars > 0 and len(thread_id) > max_chars:
        raise HTTPException(
            status_code=413,
            detail=f"thread_id is too long (max {max_chars} characters)",
        )


def _build_admin_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    function_key = os.getenv("DURABLE_FUNCTION_KEY")
    if function_key:
        headers["x-functions-key"] = function_key
    return headers


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    merged_headers = dict(headers or {})
    merged_headers.setdefault("Content-Type", "application/json")
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=merged_headers,
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    req = request.Request(url, headers=headers or {}, method="GET")
    with request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def _invoke_durable_chat(message: str, thread_id: str) -> dict:
    base_url = os.getenv("DURABLE_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("DURABLE_BASE_URL is not configured")

    start_url = f"{base_url}/api/chat/start"
    starter = _post_json(start_url, {"message": message, "thread_id": thread_id}, headers=_build_admin_headers())

    status_url = starter.get("statusQueryGetUri")
    if not status_url:
        raise RuntimeError("Durable starter response did not include statusQueryGetUri")

    # Durable's statusQueryGetUri already includes an auth `code` query param. Sending the
    # function key as an `x-functions-key` header can cause 403s on the runtime webhook.
    status_headers: dict[str, str] = {}
    if "code=" not in str(status_url):
        status_headers = _build_admin_headers()

    timeout_seconds = float(os.getenv("DURABLE_POLL_TIMEOUT", "20"))
    poll_interval = float(os.getenv("DURABLE_POLL_INTERVAL", "1.0"))
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        status = _get_json(status_url, headers=status_headers)
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


def _normalize_user(provider: str, userinfo: dict[str, Any]) -> dict[str, Any]:
    user_id = str(
        userinfo.get("sub")
        or userinfo.get("id")
        or userinfo.get("user_id")
        or userinfo.get("email")
        or "unknown"
    )
    name = userinfo.get("name") or userinfo.get("login") or userinfo.get("preferred_username")
    email = userinfo.get("email")
    picture = userinfo.get("picture") or userinfo.get("avatar_url")
    return {
        "id": user_id,
        "provider": provider,
        "name": name,
        "email": email,
        "picture": picture,
    }


def _extract_session_user(req: Request) -> dict[str, Any] | None:
    raw = req.session.get("user")
    if isinstance(raw, dict):
        return raw
    return None


def _resolve_thread_id(req: Request, explicit_thread_id: str | None) -> str:
    if explicit_thread_id:
        return explicit_thread_id

    user = _extract_session_user(req)
    user_id = str((user or {}).get("id", "")).strip()
    if user_id:
        return f"user:{user_id}"

    return str(uuid4())


def _run_chat_turn(thread_id: str, message: str) -> dict[str, Any]:
    persistence = get_persistence()
    prior_state = persistence.get_thread(thread_id)

    # Use Durable Functions only for the booking workflow (keeps Functions deps small).
    durable_error: str | None = None
    if os.getenv("DURABLE_BASE_URL"):
        is_booking_thread = isinstance(prior_state, dict) and prior_state.get("mode") == "booking"
        if is_booking_thread or is_reservation_intent(message):
            try:
                result = _invoke_durable_chat(message=message, thread_id=thread_id)
                result.setdefault("thread_id", thread_id)
                result.setdefault("mode", "info")
                result.setdefault("status", "collecting")
                result.setdefault("response", "")
                if isinstance(result, dict):
                    _maybe_record_mcp_after_durable(thread_id, result)
                return result
            except Exception as exc:
                durable_error = str(exc)

    reservation_recorder = _record_reservation_via_mcp if _mcp_recording_enabled() else None
    result, next_state = run_chat_turn(
        message=message,
        state=prior_state,
        persistence=persistence,
        answer_question=chatbot.answer_question,
        record_reservation=reservation_recorder,
    )
    persistence.upsert_thread(thread_id, next_state)

    response: dict[str, Any] = {
        **result,
        "thread_id": thread_id,
    }
    if durable_error:
        response["status_detail"] = (
            f"{(response.get('status_detail') or '').strip()} "
            "(Durable backend unavailable; using local fallback.)"
        ).strip()
    response.setdefault("response", "")
    response.setdefault("mode", "info")
    response.setdefault("status", "collecting")
    return response


def _require_admin_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("ADMIN_UI_TOKEN") or os.getenv("ADMIN_API_TOKEN")
    if expected and x_api_token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _validate_slack_signature(raw_body: bytes, req: Request) -> bool:
    signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    if not signing_secret:
        return True

    timestamp = req.headers.get("x-slack-request-timestamp", "")
    signature = req.headers.get("x-slack-signature", "")
    if not timestamp or not signature:
        return False

    base = f"v0:{timestamp}:{raw_body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


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


class GenericChannelMessageIn(BaseModel):
    channel: str
    user_id: str
    message: str
    thread_id: Optional[str] = None


class OpenAIToolMessageIn(BaseModel):
    input: str
    user_id: str
    thread_id: Optional[str] = None


@app.exception_handler(Exception)
async def handle_unexpected_exception(_req: Request, _exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/admin/health")
def admin_health() -> dict:
    return {"status": "ok", "service": "ui_admin_api"}


@app.get("/auth/providers")
def auth_providers() -> dict[str, Any]:
    return {
        "providers": [
            {"id": provider, "name": PROVIDER_TITLES.get(provider, provider.title())}
            for provider in enabled_oauth_providers
        ]
    }


@app.get("/auth/me")
def auth_me(req: Request) -> dict[str, Any]:
    user = _extract_session_user(req)
    return {"authenticated": bool(user), "user": user}


@app.post("/auth/logout")
def auth_logout(req: Request):
    req.session.pop("user", None)
    return {"ok": True}


@app.get("/auth/login/{provider}")
async def auth_login(provider: str, req: Request):
    if oauth_client is None:
        raise HTTPException(status_code=503, detail="OAuth is not enabled")

    if provider not in enabled_oauth_providers:
        raise HTTPException(status_code=404, detail="OAuth provider is not configured")

    client = oauth_client.create_client(provider)
    if client is None:
        raise HTTPException(status_code=404, detail="OAuth provider is not available")

    redirect_uri = str(req.url_for("auth_callback", provider=provider))
    return await client.authorize_redirect(req, redirect_uri)


@app.get("/auth/callback/{provider}", name="auth_callback")
@app.post("/auth/callback/{provider}", name="auth_callback_post")
async def auth_callback(provider: str, req: Request):
    if oauth_client is None or provider not in enabled_oauth_providers:
        raise HTTPException(status_code=404, detail="OAuth provider is not configured")

    client = oauth_client.create_client(provider)
    if client is None:
        raise HTTPException(status_code=404, detail="OAuth provider is not available")

    token = await client.authorize_access_token(req)
    userinfo: dict[str, Any] = {}

    try:
        # OIDC providers
        userinfo = token.get("userinfo") or await client.parse_id_token(req, token)
    except Exception:
        userinfo = {}

    if provider == "github" and not userinfo:
        user_response = await client.get("user", token=token)
        userinfo = user_response.json() if user_response else {}
        try:
            emails_response = await client.get("user/emails", token=token)
            emails = emails_response.json() if emails_response else []
            primary = next((item for item in emails if item.get("primary")), None)
            if primary and primary.get("email"):
                userinfo["email"] = primary["email"]
        except Exception:
            pass

    if not userinfo:
        userinfo = {
            "sub": token.get("sub") or token.get("access_token", "")[:12] or "unknown",
            "name": provider,
        }

    req.session["user"] = _normalize_user(provider, userinfo)
    return RedirectResponse(url="/chat/ui", status_code=302)


@app.post("/chat/ask")
def ask_chatbot(payload: ChatPromptIn, req: Request):
    enforce_rate_limit(req, scope="chat")
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    _enforce_text_limits(message, field="message")

    if is_reservation_intent(message):
        return {
            "response": (
                "Reservation request detected. Please use the admin request API "
                "or interactive booking flow to collect user booking details."
            )
        }

    try:
        return {"response": chatbot.answer_question(message)}
    except Exception:
        return {
            "response": (
                "I cannot answer right now because the AI provider is unavailable. "
                "Please retry in a moment."
            )
        }


@app.post("/chat/message")
def chat_message(payload: ChatMessageIn, req: Request):
    enforce_rate_limit(req, scope="chat")
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    _enforce_text_limits(message, field="message")

    thread_id = _resolve_thread_id(req, payload.thread_id)
    _enforce_thread_id_limits(thread_id)

    try:
        return _run_chat_turn(thread_id=thread_id, message=message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat backend error: {exc}") from exc


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
    return FileResponse(
        ui_path,
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


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
    return FileResponse(
        ui_path,
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/channels/generic/message")
def channel_generic_message(payload: GenericChannelMessageIn, req: Request):
    enforce_rate_limit(req, scope="channel")
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    _enforce_text_limits(message, field="message")

    thread_id = payload.thread_id or f"{payload.channel}:{payload.user_id}"
    _enforce_thread_id_limits(thread_id)
    result = _run_chat_turn(thread_id=thread_id, message=message)
    return {
        "channel": payload.channel,
        "user_id": payload.user_id,
        "thread_id": thread_id,
        "response": result.get("response", ""),
        "status": result.get("status", "collecting"),
    }


@app.post("/channels/openai/tool")
def openai_tool_message(payload: OpenAIToolMessageIn, req: Request):
    enforce_rate_limit(req, scope="channel")
    message = payload.input.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Input cannot be empty")
    _enforce_text_limits(message, field="input")

    thread_id = payload.thread_id or f"openai:{payload.user_id}"
    _enforce_thread_id_limits(thread_id)
    result = _run_chat_turn(thread_id=thread_id, message=message)
    return {
        "output": result.get("response", ""),
        "thread_id": thread_id,
        "status": result.get("status", "collecting"),
    }


@app.post("/channels/telegram/webhook/{token}")
def telegram_webhook(token: str, payload: dict[str, Any], req: Request):
    enforce_rate_limit(req, scope="channel")
    configured_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not configured_token:
        raise HTTPException(status_code=503, detail="Telegram bot token is not configured")
    if token != configured_token:
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook token")

    message_block = payload.get("message") or payload.get("edited_message") or {}
    chat = message_block.get("chat") or {}
    chat_id = chat.get("id")
    text = str(message_block.get("text") or "").strip()

    if not chat_id or not text:
        return {"ok": True}
    _enforce_text_limits(text, field="message")

    thread_id = f"telegram:{chat_id}"
    _enforce_thread_id_limits(thread_id)
    result = _run_chat_turn(thread_id=thread_id, message=text)

    telegram_url = f"https://api.telegram.org/bot{configured_token}/sendMessage"
    _post_json(
        telegram_url,
        {
            "chat_id": chat_id,
            "text": result.get("response", ""),
        },
    )
    return {"ok": True}


@app.post("/channels/slack/events")
async def slack_events(req: Request):
    enforce_rate_limit(req, scope="channel")
    raw_body = await req.body()
    if not _validate_slack_signature(raw_body, req):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    payload = await req.json()

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    event = payload.get("event") or {}
    if event.get("type") != "message" or event.get("bot_id"):
        return {"ok": True}

    text = str(event.get("text") or "").strip()
    user_id = str(event.get("user") or "")
    channel_id = str(event.get("channel") or "")
    if not text or not user_id or not channel_id:
        return {"ok": True}
    _enforce_text_limits(text, field="message")

    thread_id = f"slack:{channel_id}:{user_id}"
    _enforce_thread_id_limits(thread_id)
    result = _run_chat_turn(thread_id=thread_id, message=text)

    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if slack_token:
        _post_json(
            "https://slack.com/api/chat.postMessage",
            {
                "channel": channel_id,
                "text": result.get("response", ""),
            },
            headers={
                "Authorization": f"Bearer {slack_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )

    return {"ok": True}


@app.get("/channels/whatsapp/webhook")
def whatsapp_verify(
    mode: str = Query(default="", alias="hub.mode"),
    challenge: str = Query(default="", alias="hub.challenge"),
    verify_token: str = Query(default="", alias="hub.verify_token"),
):
    configured = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if mode == "subscribe" and configured and verify_token == configured:
        return int(challenge) if challenge.isdigit() else challenge
    raise HTTPException(status_code=403, detail="Invalid WhatsApp verify token")


@app.post("/channels/whatsapp/webhook")
def whatsapp_webhook(payload: dict[str, Any]):
    entries = payload.get("entry") or []
    if not entries:
        return {"ok": True}

    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    for entry in entries:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            messages = value.get("messages") or []
            for message in messages:
                from_number = str(message.get("from") or "")
                text = str((message.get("text") or {}).get("body") or "").strip()
                if not from_number or not text:
                    continue
                _enforce_text_limits(text, field="message")

                thread_id = f"whatsapp:{from_number}"
                _enforce_thread_id_limits(thread_id)
                result = _run_chat_turn(thread_id=thread_id, message=text)

                if access_token and phone_number_id:
                    _post_json(
                        f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
                        {
                            "messaging_product": "whatsapp",
                            "to": from_number,
                            "text": {"body": result.get("response", "")},
                        },
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                    )

    return {"ok": True}


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/chat/ui", status_code=307)
