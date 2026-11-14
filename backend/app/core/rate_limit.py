"""Fixed-window rate limiting.

Deliberately dependency-free and in-process. That is correct for a single
backend instance and is a meaningful improvement over no limiting at all; if you
scale horizontally, swap `InMemoryRateLimitBackend` for a Redis-backed one so the
window is shared across workers. The dependency signature does not change.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after: int


class InMemoryRateLimitBackend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: Dict[str, Tuple[int, int]] = {}  # key -> (window_start, count)
        self._last_sweep = 0.0

    def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = int(time.time())
        window_start = now - (now % window_seconds)

        with self._lock:
            self._maybe_sweep(now, window_seconds)

            start, count = self._windows.get(key, (window_start, 0))
            if start != window_start:
                start, count = window_start, 0

            count += 1
            self._windows[key] = (start, count)

        retry_after = max(1, (start + window_seconds) - now)
        return RateLimitDecision(
            allowed=count <= limit,
            remaining=max(0, limit - count),
            retry_after=retry_after,
        )

    def _maybe_sweep(self, now: int, window_seconds: int) -> None:
        """Drop expired windows so the dict cannot grow without bound."""
        if now - self._last_sweep < 60:
            return
        self._last_sweep = now
        cutoff = now - (window_seconds * 2)
        for key in [k for k, (start, _) in self._windows.items() if start < cutoff]:
            self._windows.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


_backend = InMemoryRateLimitBackend()


def get_rate_limit_backend() -> InMemoryRateLimitBackend:
    return _backend


def client_identity(request: Request) -> str:
    """Identify the caller for limiting purposes.

    Prefers the authenticated subject so one abusive user cannot exhaust the
    budget for everyone behind the same NAT. Falls back to client IP.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


def rate_limit(
    scope: str,
    limit_attr: str,
    *,
    window_seconds: int = 60,
) -> Callable:
    """Build a FastAPI dependency enforcing `limit_attr` requests per window."""

    def dependency(
        request: Request,
        settings: Settings = Depends(get_settings),
    ) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        limit: Optional[int] = getattr(settings, limit_attr, None)
        if not limit or limit <= 0:
            return

        key = f"{scope}:{client_identity(request)}"
        decision = _backend.hit(key, limit, window_seconds)

        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
                headers={"Retry-After": str(decision.retry_after)},
            )

    return dependency


# Pre-built limiters for the endpoints that need them.
auth_rate_limit = rate_limit("auth", "RATE_LIMIT_AUTH_PER_MINUTE")
chat_rate_limit = rate_limit("chat", "RATE_LIMIT_CHAT_PER_MINUTE")
upload_rate_limit = rate_limit("upload", "RATE_LIMIT_UPLOAD_PER_MINUTE")
