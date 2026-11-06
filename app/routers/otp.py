from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.otp import OTP
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.schemas.otp import OTPGenerateRequest, OTPVerifyRequest
from app.utils.otp_utils import (
    generate_otp,
    hash_otp,
    verify_otp,
    get_otp_expiry
)
from app.utils.email_utils import send_otp_email

router = APIRouter(prefix="/otp", tags=["OTP"])


@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_user_otp(
    request: OTPGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    otp = generate_otp()

    try:
        send_otp_email(current_user.email, otp)

        new_otp = OTP(
            user_id=current_user.id,
            otp_hash=hash_otp(otp),
            purpose=request.purpose,
            expires_at=get_otp_expiry(),
            is_used=False,
            attempts=0
        )

        db.add(new_otp)
        db.commit()

    except Exception as exec:
        db.rollback()
        print("OTP GENERATION ERROR:", type(exec).__name__, str(exec))
        raise HTTPException(
            status_code=500,
            detail="Failed to generate or send OTP"
        )

    return {
        "message": "OTP sent successfully to your registered email",
        "expires_in": 300
    }


@router.post("/verify")
def verify_user_otp(
    request: OTPVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    otp_record = (
        db.query(OTP)
        .filter(
            OTP.user_id == current_user.id,
            OTP.purpose == "wallet_transaction",
            OTP.is_used.is_(False)
        )
        .order_by(OTP.created_at.desc(), OTP.id.desc())
        .with_for_update()
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=404,
            detail="No active OTP found"
        )

    if otp_record.expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="OTP has expired"
        )

    if otp_record.attempts >= 3:
        raise HTTPException(
            status_code=429,
            detail="Maximum OTP verification attempts exceeded"
        )

    if not verify_otp(request.otp, otp_record.otp_hash):
        otp_record.attempts += 1
        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Invalid OTP"
        )

    otp_record.is_used = True
    db.commit()

    return {
        "message": "OTP verified successfully"
    }