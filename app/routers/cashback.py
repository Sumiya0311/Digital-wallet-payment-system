from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.cashback import Cashback

from app.auth.dependencies import (
    get_current_user,
    get_current_admin
)

from app.services.cashback_service import process_due_cashbacks


router = APIRouter(
    prefix="/cashback",
    tags=["Cashback"]
)


# --------------------------------------------------
# 1. View My Cashback
# --------------------------------------------------

@router.get("/my")
def get_my_cashback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cashbacks = (
        db.query(Cashback)
        .filter(Cashback.user_id == current_user.id)
        .order_by(Cashback.created_at.desc())
        .all()
    )

    return {
        "total": len(cashbacks),
        "cashbacks": [
            {
                "id": cashback.id,
                "transaction_id": cashback.transaction_id,
                "amount": cashback.amount,
                "status": cashback.status,
                "eligible_at": cashback.eligible_at,
                "credited_at": cashback.credited_at,
                "created_at": cashback.created_at
            }
            for cashback in cashbacks
        ]
    }


# --------------------------------------------------
# 2. Process Due Cashback (Admin Only)
# --------------------------------------------------

@router.post("/process-due")
def process_cashback(
    batch_size: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    if batch_size < 1 or batch_size > 500:
        raise HTTPException(
            status_code=400,
            detail="Batch size must be between 1 and 500"
        )

    try:
        result = process_due_cashbacks(
            db=db,
            batch_size=batch_size
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Cashback processing failed"
        )