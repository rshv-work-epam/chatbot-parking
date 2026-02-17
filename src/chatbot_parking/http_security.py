"""HTTP security helpers (rate limiting + security headers).

This is intentionally lightweight. In real production you typically enforce these
controls at the edge (Azure Front Door / WAF, API Management), but having an
application-level layer provides defense-in-depth and makes local dev safer.
"""

from __future__ import annotations

from collections import deque
import os
import threading
import time
from typing import Deque, Tuple

from fastapi import HTTPException, Request, Response


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _rate_limit_enabled() -> bool:
    # Default: enabled in prod, disabled in dev/test unless explicitly turned on.
    if os.getenv("RATE_LIMIT_ENABLED") is not None:
        return _env_bool("RATE_LIMIT_ENABLED", False)
    return os.getenv("APP_ENV", "dev").strip().lower() == "prod"


def client_ip(req: Request) -> str:
    forwarded = req.headers.get("x-forwarded-for", "")
    if forwarded:
        # XFF can contain a list. Use the first (original) hop.
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return (req.client.host if req.client else "unknown").strip() or "unknown"


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(1, int(window_seconds))
        self._hits: dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "SlidingWindowRateLimiter":
        max_requests = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60"))
        window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
        return cls(max_requests=max_requests, window_seconds=window_seconds)

    def allow(self, key: str) -> Tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - float(self.window_seconds)
        retry_after = 0

        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = deque()
                self._hits[key] = hits

            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.max_requests:
                retry_after = int(self.window_seconds - max(0.0, now - hits[0]))
                return (False, max(1, retry_after))

            hits.append(now)
            return (True, 0)


_RATE_LIMITER = SlidingWindowRateLimiter.from_env()

def reset_rate_limiter(*, max_requests: int | None = None, window_seconds: int | None = None) -> None:
    """Test helper to reconfigure the process-local limiter."""
    global _RATE_LIMITER
    _RATE_LIMITER = SlidingWindowRateLimiter(
        max_requests=max_requests or _RATE_LIMITER.max_requests,
        window_seconds=window_seconds or _RATE_LIMITER.window_seconds,
    )


def enforce_rate_limit(req: Request, *, scope: str = "chat") -> None:
    if not _rate_limit_enabled():
        return

    key = f"{scope}:{client_ip(req)}"
    allowed, retry_after = _RATE_LIMITER.allow(key)
    if allowed:
        return

    raise HTTPException(
        status_code=429,
        detail="Rate limit exceeded. Please retry shortly.",
        headers={"Retry-After": str(retry_after)},
    )


def apply_security_headers(req: Request, resp: Response) -> None:
    """Set basic security headers (OWASP-friendly defaults)."""

    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

    # Dictation uses microphone. Keep other features off by default.
    resp.headers.setdefault(
        "Permissions-Policy",
        "microphone=(self), geolocation=(), camera=(), payment=(), usb=()",
    )

    # Our UI uses inline scripts/styles; keep CSP restrictive but compatible.
    if _env_bool("CSP_ENABLED", True):
        resp.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "connect-src 'self'; "
                "img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; "
                "base-uri 'none'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            ),
        )

    # Avoid caching chat/admin responses by default in prod.
    if os.getenv("APP_ENV", "dev").strip().lower() == "prod":
        resp.headers.setdefault("Cache-Control", "no-store")

    # HSTS only makes sense when TLS is actually in use.
    forwarded_proto = req.headers.get("x-forwarded-proto", "").lower()
    if forwarded_proto == "https":
        resp.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
