from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.user import User
from app.models.bank_account import BankAccount

from app.schemas.bank_account import (
    BankAccountCreate,
    BankAccountResponse
)

from app.auth.dependencies import get_current_user

from app.services.bank_account_service import (
    register_bank_account
)


router = APIRouter(
    prefix="/bank-accounts",
    tags=["Bank Accounts"]
)


# 1. Register bank account
@router.post(
    "/register",
    response_model=BankAccountResponse,
    status_code=status.HTTP_201_CREATED
)
def add_bank_account(
    bank_data: BankAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return register_bank_account(
            db=db,
            current_user=current_user,
            bank_data=bank_data
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bank account already exists"
        )


# 2. List my bank accounts
@router.get(
    "/my-accounts",
    response_model=list[BankAccountResponse]
)
def get_my_bank_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return (
        db.query(BankAccount)
        .filter(BankAccount.user_id == current_user.id)
        .order_by(BankAccount.id.desc())
        .all()
    )