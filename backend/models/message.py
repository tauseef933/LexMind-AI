"""API schemas for chat messages."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: Optional[str]
    role: str
    content: str
    agent_trace: Optional[list[dict[str, Any]]] = None
    sources: Optional[list[Any]] = None
    created_at: datetime


class ChatRequest(BaseModel):
    content: str
    case_id: str
    case_name: str = "Unknown Case"
