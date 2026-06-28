"""
POST /chat — SSE streaming chat endpoint.

Stream sequence:
  1. {"type": "agent_trace", "step": {"agent": "orchestrator", "status": "routing"}}
  2. Per-agent firing events
  3. {"type": "token", "content": "word "} — response word-by-word
  4. {"type": "done", "sources": [...]}

Persists completed message to SQLite messages table.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.agents.orchestrator import process
from backend.models.database import Message, get_db

logger = logging.getLogger("lexmind.chat")

router = APIRouter(tags=["chat"])


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    content: str
    case_id: str
    case_name: str = "Unknown Case"


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------
def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# Streaming generator
# ---------------------------------------------------------------------------
async def _stream_chat(
    request: ChatRequest,
    db: Session,
) -> AsyncGenerator[str, None]:
    # Persist user message immediately so history survives refresh
    user_msg_id = str(uuid.uuid4())
    try:
        user_msg = Message(
            id=user_msg_id,
            case_id=request.case_id,
            role="user",
            content=request.content,
            agent_trace=None,
            sources=None,
            created_at=datetime.utcnow(),
        )
        db.add(user_msg)
        db.commit()
    except Exception as exc:
        logger.error("Failed to persist user message: %s", exc)
        db.rollback()

    # Step a — routing notice
    yield _sse({
        "type": "agent_trace",
        "step": {"agent": "orchestrator", "status": "routing"},
    })

    # Run orchestrator synchronously (LangGraph is sync; SSE wrapper is async)
    try:
        result = process(
            query=request.content,
            case_id=request.case_id,
            case_name=request.case_name,
        )
    except Exception as exc:
        logger.error("Orchestrator error: %s", exc, exc_info=True)
        yield _sse({"type": "error", "content": str(exc)})
        return

    agent_trace: list[dict] = result.get("agent_trace", [])
    sources: list = result.get("sources", [])
    response_text: str = result.get("response", "")

    # Step b — per-agent firing events
    for agent_result in agent_trace:
        agent_name = agent_result.get("agent", "unknown")
        status = "error" if "error" in agent_result else "done"
        yield _sse({
            "type": "agent_trace",
            "step": {"agent": agent_name, "status": status},
        })

    # Step c — stream response word-by-word
    words = response_text.split(" ")
    for word in words:
        yield _sse({"type": "token", "content": word + " "})

    # Step d — done event with sources
    yield _sse({"type": "done", "sources": sources})

    # Persist assistant message to SQLite
    try:
        msg = Message(
            id=str(uuid.uuid4()),
            case_id=request.case_id,
            role="assistant",
            content=response_text,
            agent_trace=json.dumps(agent_trace),
            sources=json.dumps(sources),
            created_at=datetime.utcnow(),
        )
        db.add(msg)
        db.commit()
    except Exception as exc:
        logger.error("Failed to persist assistant message: %s", exc)
        db.rollback()


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    return StreamingResponse(
        _stream_chat(request, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
