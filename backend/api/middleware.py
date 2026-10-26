import hmac
import logging
import os
import re
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from logging_setup import request_id_var

logger = logging.getLogger("lexmind")

# ---------------------------------------------------------------------------
# CORS origins helper — consumed by main.py
# ---------------------------------------------------------------------------
def get_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


# ---------------------------------------------------------------------------
# Request logging middleware — assigns a request ID, logs method/path/timing
# ---------------------------------------------------------------------------
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Reuse a caller-supplied ID (e.g. from a proxy) if it looks sane
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "%s %s → %s  (%.1f ms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                extra={"method": request.method, "path": request.url.path,
                       "status": response.status_code, "duration_ms": round(elapsed_ms, 1)},
            )
            return response
        except Exception:
            logger.exception("%s %s → unhandled error", request.method, request.url.path)
            raise
        finally:
            request_id_var.reset(token)


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
        if not hmac.compare_digest(provided.encode(), self._key.encode()):
            return Response(
                content='{"detail":"Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)
