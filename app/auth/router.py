import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.models.account import Account

from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse
)

from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)



@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED
)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        (User.email == user_data.email) |
        (User.phone == user_data.phone)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or phone number already registered"
        )

    try:
        
        new_user = User(
            full_name=user_data.full_name,
            email=user_data.email,
            phone=user_data.phone,
            hashed_password=hash_password(user_data.password),
            role="User"
        )

        db.add(new_user)
        db.flush()

        
        wallet_number = (
            f"WAL-{secrets.randbelow(9000000) + 1000000}"
        )

        
        wallet = Wallet(
            owner_id=new_user.id,
            wallet_number=wallet_number,
            balance=0,
            kyc_level="Minimum",
            status="Active"
        )

        db.add(wallet)
        db.flush()

        
        wallet_account = Account(
            account_type="User Wallet",
            wallet_id=wallet.id,
            balance=0
        )

        db.add(wallet_account)

        
        db.commit()

        db.refresh(new_user)
        db.refresh(wallet)

        return {
            "message": "User registered successfully",
            "user_id": new_user.id,
            "full_name": new_user.full_name,
            "email": new_user.email,
            "phone": new_user.phone,
            "wallet_number": wallet.wallet_number,
            "wallet_balance": str(wallet.balance),
            "kyc_level": wallet.kyc_level
        }

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email, phone or wallet number already exists"
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )



@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    
    if not user or not verify_password(
        user_data.password,
        user.hashed_password
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    
    if not user.is_active:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }