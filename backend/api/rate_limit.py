"""
Per-client rate limiting for the expensive endpoints (LLM calls, uploads).

A sliding-window limiter kept in memory — enough for a single-instance
deployment. Behind several instances, swap the store for Redis.

Settings (env):
  RATE_LIMIT_ENABLED   "true" (default) / "false"
  RATE_LIMIT_SCALE     multiply every limit, e.g. 2 to double them (default 1)
  TRUST_PROXY          "true" to take the client IP from X-Forwarded-For
                       (only behind a proxy you control, e.g. Railway, nginx)
"""

import os
import re
import threading
import time
from collections import defaultdict, deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# (method, path regex, requests allowed, per seconds)
_RULES: list[tuple[str, re.Pattern, int, int]] = [
    ("POST", re.compile(r"^/chat$"), 20, 60),
    ("POST", re.compile(r"^/upload$"), 30, 60),
    ("GET", re.compile(r"^/cases/[^/]+/(summary|risks|timeline|suggestions)$"), 15, 60),
    ("POST", re.compile(r"^/cases/[^/]+/(prep|reports/pdf)$"), 10, 60),
]


def _enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").lower() not in {"0", "false", "no"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        scale = float(os.getenv("RATE_LIMIT_SCALE", "1"))
        self._rules = [(m, p, max(1, int(n * scale)), w) for m, p, n, w in _RULES]
        self._trust_proxy = os.getenv("TRUST_PROXY", "false").lower() == "true"
        self._hits: dict[tuple[str, int], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _client_ip(self, request: Request) -> str:
        if self._trust_proxy:
            forwarded = request.headers.get("X-Forwarded-For", "")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if not _enabled():
            return await call_next(request)

        path = request.url.path
        for index, (method, pattern, limit, window) in enumerate(self._rules):
            if request.method != method or not pattern.match(path):
                continue

            now = time.monotonic()
            key = (self._client_ip(request), index)
            with self._lock:
                hits = self._hits[key]
                while hits and hits[0] <= now - window:
                    hits.popleft()
                if len(hits) >= limit:
                    retry_after = int(hits[0] + window - now) + 1
                    return Response(
                        content='{"detail":"Too many requests. Please wait and try again."}',
                        status_code=429,
                        media_type="application/json",
                        headers={"Retry-After": str(retry_after)},
                    )
                hits.append(now)
            break

        return await call_next(request)
