from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_admin
from app.services.cashback_funding_service import fund_cashback_pool


router = APIRouter(
    prefix="/cashback",
    tags=["Cashback Funding"]
)


class CashbackFundingRequest(BaseModel):
    amount: Decimal = Field(
        default=Decimal("100.00"),
        gt=0,
        max_digits=12,
        decimal_places=2
    )


@router.post("/fund")
def fund_cashback(
    request: CashbackFundingRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    try:
        return fund_cashback_pool(
            db=db,
            admin=admin,
            amount=request.amount
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Cashback Pool funding failed"
        )