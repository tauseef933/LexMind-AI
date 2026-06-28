from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import Billing, get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------
class BillingOut(BaseModel):
    id: str
    case_id: Optional[str]
    invoice_number: Optional[str]
    amount: Optional[float]
    hours: Optional[float]
    invoice_date: Optional[date]
    dispute_flag: Optional[bool]
    dispute_reason: Optional[str]
    status: Optional[str]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# GET /analytics/billing — return billing rows, optionally filtered by case
# ---------------------------------------------------------------------------
@router.get("/billing", response_model=list[BillingOut])
def get_billing(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Billing)
    if case_id:
        query = query.filter(Billing.case_id == case_id)
    return query.order_by(Billing.invoice_date.desc()).all()
