"""
POST /chat — SSE streaming chat endpoint.

Stream sequence (all events come live from the orchestrator):
  1. {"type": "agent_trace", "step": {"agent": "orchestrator", "status": "routing"}}
  2. {"type": "agent_trace", "step": {"agent": "<agent>", "status": "running" | "done" | "error"}}
  3. {"type": "token", "content": "..."} — answer text as the LLM generates it
  4. {"type": "done", "sources": [...], "actions": [...]}

The last few messages of the case are sent along as conversation history so
follow-up questions ("what about the second clause?") are understood.

Persists both messages to the SQLite messages table.
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import iterate_in_threadpool, run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agents.orchestrator import stream_events
from models.database import Case, Message, SessionLocal, get_db, utcnow
from models.message import ChatRequest

logger = logging.getLogger("lexmind.chat")

router = APIRouter(tags=["chat"])

_HISTORY_MESSAGES = 6   # earlier messages passed to the orchestrator


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------
def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------
def _save_message(message: Message) -> None:
    # The request-scoped session from Depends(get_db) is closed before a
    # StreamingResponse body runs, so each write uses its own session.
    db = SessionLocal()
    try:
        db.add(message)
        db.commit()
    except Exception:
        logger.exception("Failed to persist %s message", message.role)
        db.rollback()
    finally:
        db.close()


def _recent_history(db: Session, case_id: str) -> list[dict]:
    rows = (
        db.query(Message)
        .filter(Message.case_id == case_id)
        .order_by(Message.created_at.desc())
        .limit(_HISTORY_MESSAGES)
        .all()
    )
    return [
        {"role": row.role or "user", "content": row.content or ""}
        for row in reversed(rows)
        if row.content
    ]


# ---------------------------------------------------------------------------
# Streaming generator
# ---------------------------------------------------------------------------
async def _stream_chat(request: ChatRequest, history: list[dict]) -> AsyncGenerator[str, None]:
    # Persist user message immediately so history survives refresh
    await run_in_threadpool(_save_message, Message(
        id=str(uuid.uuid4()),
        case_id=request.case_id,
        role="user",
        content=request.content,
        agent_trace=None,
        sources=None,
        created_at=utcnow(),
    ))

    # The LangGraph pipeline is sync — each step of the generator runs in a
    # worker thread so the event loop keeps serving other requests.
    events = stream_events(
        query=request.content,
        case_id=request.case_id,
        case_name=request.case_name,
        history=history,
    )
    final: dict = {}
    try:
        async for event in iterate_in_threadpool(events):
            if event["type"] == "final":
                final = event
            else:
                yield _sse(event)
    except Exception:
        logger.exception("Orchestrator error")
        yield _sse({"type": "error", "content": "Something went wrong while answering. Please try again."})
        return

    yield _sse({
        "type": "done",
        "sources": final.get("sources", []),
        "actions": final.get("actions", []),
    })

    # Persist assistant message to SQLite
    await run_in_threadpool(_save_message, Message(
        id=str(uuid.uuid4()),
        case_id=request.case_id,
        role="assistant",
        content=final.get("response", ""),
        agent_trace=json.dumps(final.get("agent_trace", []), default=str),
        sources=json.dumps(final.get("sources", []), default=str),
        created_at=utcnow(),
    ))


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.post("/chat")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if not db.query(Case.id).filter(Case.id == request.case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    history = _recent_history(db, request.case_id)
    return StreamingResponse(
        _stream_chat(request, history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
