from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.schemas.transaction import (
    P2PTransferRequest,
    TransactionResponse
)
from app.services.p2p_service import execute_p2p_transfer


router = APIRouter(
    prefix="/p2p",
    tags=["P2P Transfers"]
)


@router.post(
    "/transfer",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED
)
def transfer_money(
    request: P2PTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        transaction = execute_p2p_transfer(
            db=db,
            sender=current_user,
            receiver_wallet_number=request.receiver_wallet_number,
            amount=request.amount,
            pin=request.pin,
            otp=request.otp,
            idempotency_key=request.idempotency_key,
            description=request.description
        )

        return transaction

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transfer failed. Please try again."
        )