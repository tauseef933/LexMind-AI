import json
import uuid
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import Case, Message, get_db
from services.case_summary import generate_summary
from services.risk_detector import detect_risks
from services.timeline_builder import build_timeline
from services.hearing_prep import prepare_hearing

router = APIRouter(prefix="/cases", tags=["cases"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class CaseCreate(BaseModel):
    name: str
    client: Optional[str] = None
    court: Optional[str] = None
    hearing_date: Optional[date] = None
    status: Optional[str] = "active"


class CaseOut(BaseModel):
    id: str
    name: str
    client: Optional[str]
    court: Optional[str]
    hearing_date: Optional[date]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# GET /cases — list all non-archived cases
# ---------------------------------------------------------------------------
@router.get("", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db)):
    return db.query(Case).filter(Case.status != "archived").order_by(Case.created_at.desc()).all()


# ---------------------------------------------------------------------------
# POST /cases — create a new case
# ---------------------------------------------------------------------------
@router.post("", response_model=CaseOut, status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    case = Case(
        id=str(uuid.uuid4()),
        name=payload.name,
        client=payload.client,
        court=payload.court,
        hearing_date=payload.hearing_date,
        status=payload.status or "active",
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


# ---------------------------------------------------------------------------
# GET /cases/{id} — single case
# ---------------------------------------------------------------------------
@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


# ---------------------------------------------------------------------------
# DELETE /cases/{id} — soft delete (status → archived)
# ---------------------------------------------------------------------------
@router.delete("/{case_id}", status_code=200)
def archive_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case.status = "archived"
    case.updated_at = datetime.utcnow()
    db.commit()
    return {"id": case_id, "status": "archived"}


# ---------------------------------------------------------------------------
# GET /cases/{id}/messages — chat history for a case
# ---------------------------------------------------------------------------
class MessageOut(BaseModel):
    id: str
    case_id: Optional[str]
    role: str
    content: str
    agent_trace: Optional[list[dict[str, Any]]] = None
    sources: Optional[list[dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{case_id}/messages", response_model=list[MessageOut])
def list_messages(case_id: str, db: Session = Depends(get_db)):
    _require_case(case_id, db)
    rows = (
        db.query(Message)
        .filter(Message.case_id == case_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    out: list[MessageOut] = []
    for row in rows:
        agent_trace = json.loads(row.agent_trace) if row.agent_trace else None
        sources = json.loads(row.sources) if row.sources else None
        out.append(
            MessageOut(
                id=row.id,
                case_id=row.case_id,
                role=row.role,
                content=row.content,
                agent_trace=agent_trace,
                sources=sources,
                created_at=row.created_at,
            )
        )
    return out


# ---------------------------------------------------------------------------
# GET /cases/{id}/summary
# ---------------------------------------------------------------------------
@router.get("/{case_id}/summary")
def case_summary(case_id: str, db: Session = Depends(get_db)):
    _require_case(case_id, db)
    return generate_summary(case_id)


# ---------------------------------------------------------------------------
# GET /cases/{id}/timeline
# ---------------------------------------------------------------------------
@router.get("/{case_id}/timeline")
def case_timeline(case_id: str, db: Session = Depends(get_db)):
    _require_case(case_id, db)
    return {"timeline": build_timeline(case_id)}


# ---------------------------------------------------------------------------
# GET /cases/{id}/risks
# ---------------------------------------------------------------------------
@router.get("/{case_id}/risks")
def case_risks(case_id: str, db: Session = Depends(get_db)):
    _require_case(case_id, db)
    return detect_risks(case_id)


# ---------------------------------------------------------------------------
# POST /cases/{id}/prep
# ---------------------------------------------------------------------------
class PrepRequest(BaseModel):
    hearing_date: str  # e.g. "2026-09-15"


@router.post("/{case_id}/prep")
def case_prep(case_id: str, body: PrepRequest, db: Session = Depends(get_db)):
    _require_case(case_id, db)
    return prepare_hearing(case_id, body.hearing_date)


# ---------------------------------------------------------------------------
# Shared guard
# ---------------------------------------------------------------------------
def _require_case(case_id: str, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case
