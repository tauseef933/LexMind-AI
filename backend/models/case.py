"""API schemas for cases."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CaseCreate(BaseModel):
    name: str
    client: Optional[str] = None
    court: Optional[str] = None
    hearing_date: Optional[date] = None
    status: Optional[str] = "active"


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    client: Optional[str]
    court: Optional[str]
    hearing_date: Optional[date]
    status: str
    created_at: datetime
    updated_at: datetime


class PrepRequest(BaseModel):
    hearing_date: str  # e.g. "2026-09-15"


class ReportSection(BaseModel):
    heading: str = Field(default="", max_length=300)
    content: str = Field(default="", max_length=20_000)


class ReportRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    sections: list[ReportSection] = Field(default_factory=list, max_length=50)
