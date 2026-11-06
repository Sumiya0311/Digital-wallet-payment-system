from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.wallet import Wallet
from app.models.user import User
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction

from app.schemas.wallet import (
    WalletResponse,
    WalletPinCreate,
    WalletPinVerify,
    WalletPinChange
)

from app.auth.dependencies import get_current_user
from app.auth.utils import hash_password, verify_password


router = APIRouter(
    prefix="/wallet",
    tags=["Wallet"]
)


# --------------------------------------------------
# 1. Get My Wallet
# --------------------------------------------------

@router.get("/", response_model=WalletResponse)
def get_my_wallet(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wallet = db.query(Wallet).filter(
        Wallet.owner_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )

    return wallet


# --------------------------------------------------
# 2. Get Wallet Balance
# --------------------------------------------------

@router.get("/balance")
def get_wallet_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wallet = db.query(Wallet).filter(
        Wallet.owner_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )

    return {
        "wallet_number": wallet.wallet_number,
        "balance": wallet.balance,
        "currency": "INR"
    }


# --------------------------------------------------
# 3. Set Wallet PIN
# --------------------------------------------------

@router.post(
    "/set-pin",
    status_code=status.HTTP_201_CREATED
)
def set_wallet_pin(
    pin_data: WalletPinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wallet = db.query(Wallet).filter(
        Wallet.owner_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )

    if wallet.pin_hash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wallet PIN is already set"
        )

    wallet.pin_hash = hash_password(pin_data.pin)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set wallet PIN"
        )

    return {
        "message": "Wallet PIN set successfully"
    }


# --------------------------------------------------
# 4. Verify Wallet PIN
# --------------------------------------------------

@router.post("/verify-pin")
def verify_wallet_pin(
    pin_data: WalletPinVerify,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == current_user.id)
        .with_for_update()
        .first()
    )

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    if not wallet.pin_hash:
        raise HTTPException(
            status_code=400,
            detail="Wallet PIN is not set"
        )

    now = datetime.now(timezone.utc)

    if wallet.pin_locked_until:
        locked_until = wallet.pin_locked_until.replace(
            tzinfo=timezone.utc
        )

        if now < locked_until:
            remaining_seconds = max(
                0,
                int((locked_until - now).total_seconds())
            )

            raise HTTPException(
                status_code=423,
                detail=(
                    "Wallet is locked. Try again in "
                    f"{remaining_seconds} seconds."
                )
            )

        wallet.pin_locked_until = None
        wallet.failed_pin_attempts = 0

    if not verify_password(
        pin_data.pin,
        wallet.pin_hash
    ):
        wallet.failed_pin_attempts += 1

        if wallet.failed_pin_attempts >= 3:
            wallet.pin_locked_until = (
                datetime.now(timezone.utc)
                + timedelta(minutes=5)
            )

            db.commit()

            raise HTTPException(
                status_code=423,
                detail=(
                    "Too many incorrect PIN attempts. "
                    "Wallet locked for 5 minutes."
                )
            )

        remaining_attempts = (
            3 - wallet.failed_pin_attempts
        )

        db.commit()

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid wallet PIN. "
                f"{remaining_attempts} attempts remaining."
            )
        )

    wallet.failed_pin_attempts = 0
    wallet.pin_locked_until = None

    db.commit()

    return {
        "message": "Wallet PIN verified successfully"
    }


# --------------------------------------------------
# 5. Change Wallet PIN
# --------------------------------------------------

@router.post("/change-pin")
def change_wallet_pin(
    pin_data: WalletPinChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == current_user.id)
        .with_for_update()
        .first()
    )

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    if not wallet.pin_hash:
        raise HTTPException(
            status_code=400,
            detail="Wallet PIN is not set"
        )

    now = datetime.now(timezone.utc)

    if wallet.pin_locked_until:
        locked_until = wallet.pin_locked_until.replace(
            tzinfo=timezone.utc
        )

        if now < locked_until:
            raise HTTPException(
                status_code=423,
                detail=(
                    "Wallet is locked. Try again after "
                    "the lockout expires."
                )
            )

        wallet.pin_locked_until = None
        wallet.failed_pin_attempts = 0

    if not verify_password(
        pin_data.current_pin,
        wallet.pin_hash
    ):
        wallet.failed_pin_attempts += 1

        if wallet.failed_pin_attempts >= 3:
            wallet.pin_locked_until = (
                datetime.now(timezone.utc)
                + timedelta(minutes=5)
            )

            db.commit()

            raise HTTPException(
                status_code=423,
                detail=(
                    "Too many incorrect PIN attempts. "
                    "Wallet locked for 5 minutes."
                )
            )

        remaining = 3 - wallet.failed_pin_attempts

        db.commit()

        raise HTTPException(
            status_code=401,
            detail=(
                "Current PIN is incorrect. "
                f"{remaining} attempts remaining."
            )
        )

    if verify_password(
        pin_data.new_pin,
        wallet.pin_hash
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "New PIN must be different "
                "from current PIN"
            )
        )

    wallet.pin_hash = hash_password(
        pin_data.new_pin
    )
    wallet.failed_pin_attempts = 0
    wallet.pin_locked_until = None

    try:
        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to change wallet PIN"
        )

    return {
        "message": "Wallet PIN changed successfully"
    }


# --------------------------------------------------
# 6. Get Wallet Statement
# --------------------------------------------------

@router.get("/statement")
def get_wallet_statement(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Find authenticated user's wallet
    wallet = db.query(Wallet).filter(
        Wallet.owner_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    # Find account associated with wallet
    account = db.query(Account).filter(
        Account.wallet_id == wallet.id
    ).first()

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Wallet ledger account not found"
        )

    # Fetch wallet-specific ledger records
    query = (
        db.query(LedgerEntry, Transaction)
        .join(
            Transaction,
            LedgerEntry.transaction_id == Transaction.id
        )
        .filter(
            LedgerEntry.account_id == account.id
        )
    )

    total = query.count()

    records = (
        query.order_by(
            LedgerEntry.created_at.desc(),
            LedgerEntry.id.desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    statement = []

    for entry, transaction in records:

        # User and merchant wallet accounts
        # are credit-normal.
        if entry.entry_type == "Credit":
            direction = "Incoming"
        else:
            direction = "Outgoing"

        statement.append({
            "transaction_id": transaction.id,
            "transaction_ref": transaction.transaction_ref,
            "transaction_type": transaction.type,
            "status": transaction.status,
            "direction": direction,
            "entry_type": entry.entry_type,
            "amount": str(entry.amount),
            "balance_after": str(entry.balance_after),
            "description": transaction.description,
            "created_at": entry.created_at
        })

    return {
        "wallet_number": wallet.wallet_number,
        "currency": "INR",
        "current_balance": str(wallet.balance),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (
            total + page_size - 1
        ) // page_size,
        "statement": statement
    }