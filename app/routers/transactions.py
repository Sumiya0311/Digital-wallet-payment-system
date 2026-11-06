from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.transaction import Transaction

from app.auth.dependencies import (
    get_current_user,
    get_current_admin
)

from app.schemas.transaction import (
    AddMoneyRequest,
    WithdrawalRequest,
    WithdrawalReversalRequest,
    TransactionResponse
)

from app.services.add_money_service import execute_add_money
from app.services.withdrawal_service import process_withdrawal
from app.services.withdrawal_reversal_service import (
    process_withdrawal_reversal
)


router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


# --------------------------------------------------
# 1. Add Money
# --------------------------------------------------

@router.post(
    "/add-money",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED
)
def add_money(
    request: AddMoneyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return execute_add_money(
            db=db,
            user=current_user,
            amount=request.amount,
            idempotency_key=request.idempotency_key,
            description=request.description
        )

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
            detail="Add money failed. Please try again."
        )


# --------------------------------------------------
# 2. Wallet Withdrawal
# --------------------------------------------------

@router.post(
    "/withdraw",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED
)
def withdraw_money(
    request: WithdrawalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return process_withdrawal(
            db=db,
            customer=current_user,
            bank_account_id=request.bank_account_id,
            amount=request.amount,
            pin=request.pin,
            idempotency_key=request.idempotency_key,
            description=request.description
        )

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
            detail="Withdrawal failed. Please try again."
        )

# --------------------------------------------------
# 3. My Transaction History
# --------------------------------------------------

@router.get("/history")
def get_transaction_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    transaction_type: Optional[str] = None,
    transaction_status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date cannot be after end date"
        )

    query = db.query(Transaction).filter(
        Transaction.initiated_by == current_user.id
    )

    if transaction_type:
        query = query.filter(
            Transaction.type == transaction_type
        )

    if transaction_status:
        query = query.filter(
            Transaction.status == transaction_status
        )

    if start_date:
        query = query.filter(
            Transaction.created_at >= start_date
        )

    if end_date:
        query = query.filter(
            Transaction.created_at <= end_date
        )

    total = query.count()

    transactions = (
        query.order_by(
            Transaction.created_at.desc(),
            Transaction.id.desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "transactions": [
            {
                "id": txn.id,
                "transaction_ref": txn.transaction_ref,
                "type": txn.type,
                "amount": str(txn.amount),
                "status": txn.status,
                "description": txn.description,
                "created_at": txn.created_at
            }
            for txn in transactions
        ]
    }