import logging
import os
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("lexmind")

# ---------------------------------------------------------------------------
# CORS origins helper — consumed by main.py
# ---------------------------------------------------------------------------
def get_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %s  (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


# ---------------------------------------------------------------------------
# API-key guard middleware
# Requests to /api/* must carry  X-API-Key: <SECRET_KEY>
# All other paths (health, docs, openapi.json) are let through freely.
# ---------------------------------------------------------------------------
OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret_key: str):
        super().__init__(app)
        self._key = secret_key

    async def dispatch(self, request: Request, call_next) -> Response:
        # Let CORS preflight through without an API key
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in OPEN_PATHS or not self._key:
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if provided != self._key:
            return Response(
                content='{"detail":"Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)
