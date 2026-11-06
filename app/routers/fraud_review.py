from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.fraud_flag import FraudFlag
from app.auth.dependencies import get_current_admin
from app.services.fraud_review_service import (
    review_fraud_transaction
)


router = APIRouter(
    prefix="/admin/fraud",
    tags=["Admin Fraud Review"]
)


class FraudReviewRequest(BaseModel):
    notes: str = Field(default="", max_length=1000)


@router.get("/pending")
def list_pending_fraud_flags(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    flags = (
        db.query(FraudFlag)
        .filter(FraudFlag.status == "Pending")
        .order_by(FraudFlag.created_at.desc())
        .all()
    )

    return [
        {
            "fraud_flag_id": flag.id,
            "transaction_id": flag.transaction_id,
            "user_id": flag.user_id,
            "reason": flag.reason,
            "status": flag.status
        }
        for flag in flags
    ]


@router.post("/{transaction_id}/approve")
def approve_fraud_transaction(
    transaction_id: int,
    request: FraudReviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    try:
        transaction = review_fraud_transaction(
            db=db,
            admin=admin,
            transaction_id=transaction_id,
            decision="Approved",
            notes=request.notes
        )

        return {
            "message": "Fraud transaction approved",
            "transaction_id": transaction.id,
            "status": transaction.status
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


@router.post("/{transaction_id}/reject")
def reject_fraud_transaction(
    transaction_id: int,
    request: FraudReviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    try:
        transaction = review_fraud_transaction(
            db=db,
            admin=admin,
            transaction_id=transaction_id,
            decision="Rejected",
            notes=request.notes
        )

        return {
            "message": "Fraud transaction rejected",
            "transaction_id": transaction.id,
            "status": transaction.status
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )