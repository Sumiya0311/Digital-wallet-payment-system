from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import secrets
import qrcode
from io import BytesIO

from app.database import get_db
from app.models.user import User
from app.models.merchant import Merchant

from app.schemas.merchant import (
    MerchantCreate,
    MerchantResponse
)

from app.schemas.transaction import (
    MerchantPaymentRequest,
    MerchantRefundRequest,
    TransactionResponse
)

from app.auth.dependencies import (
    get_current_user,
    get_current_admin
)

from app.services.merchant_payment_service import (
    make_merchant_payment
)

from app.services.merchant_refund_service import (
    process_merchant_refund
)


router = APIRouter(
    prefix="/merchants",
    tags=["Merchants"]
)


# --------------------------------------------------
# 1. Register Merchant (Admin Only)
# --------------------------------------------------

@router.post(
    "/register",
    response_model=MerchantResponse,
    status_code=status.HTTP_201_CREATED
)
def register_merchant(
    merchant_data: MerchantCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    user = db.query(User).filter(
        User.id == merchant_data.user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="User account is inactive"
        )

    if user.role == "Admin":
        raise HTTPException(
            status_code=400,
            detail="Admin cannot be registered as a merchant"
        )

    existing = db.query(Merchant).filter(
        Merchant.user_id == user.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Merchant already registered for this user"
        )

    merchant = Merchant(
        user_id=user.id,
        business_name=merchant_data.business_name,
        business_category=merchant_data.business_category,
        merchant_code=f"MER-{secrets.token_hex(6).upper()}",
        is_verified=False
    )

    try:
        user.role = "Merchant"
        db.add(merchant)
        db.commit()
        db.refresh(merchant)

        return merchant

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Merchant registration failed"
        )


# --------------------------------------------------
# 2. Verify Merchant (Admin Only)
# --------------------------------------------------

@router.post("/{merchant_id}/verify")
def verify_merchant(
    merchant_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    merchant = db.query(Merchant).filter(
        Merchant.id == merchant_id
    ).first()

    if not merchant:
        raise HTTPException(
            status_code=404,
            detail="Merchant not found"
        )

    merchant.is_verified = True

    db.commit()
    db.refresh(merchant)

    return {
        "message": "Merchant verified successfully",
        "merchant_id": merchant.id,
        "merchant_code": merchant.merchant_code,
        "is_verified": merchant.is_verified
    }


# --------------------------------------------------
# 3. Get Merchant QR Code
# --------------------------------------------------

@router.get("/me/qr")
def get_merchant_qr(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "Merchant":
        raise HTTPException(
            status_code=403,
            detail="Only merchants can access their QR code"
        )

    merchant = db.query(Merchant).filter(
        Merchant.user_id == current_user.id
    ).first()

    if not merchant:
        raise HTTPException(
            status_code=404,
            detail="Merchant profile not found"
        )

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )

    qr.add_data(merchant.merchant_code)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)

    return StreamingResponse(
        image_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f'inline; filename="{merchant.merchant_code}.png"'
            )
        }
    )


# --------------------------------------------------
# 4. Merchant Payment
# --------------------------------------------------

@router.post(
    "/pay",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED
)
def pay_merchant(
    payment_data: MerchantPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        transaction = make_merchant_payment(
            db=db,
            customer=current_user,
            merchant_code=payment_data.merchant_code,
            amount=payment_data.amount,
            pin=payment_data.pin,
            otp_code=payment_data.otp,
            idempotency_key=payment_data.idempotency_key,
            description=payment_data.description
        )

        return transaction

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# --------------------------------------------------
# 5. Merchant Refund
# --------------------------------------------------

@router.post(
    "/refund",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED
)
def refund_merchant_payment(
    refund_data: MerchantRefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        transaction = process_merchant_refund(
            db=db,
            merchant_user=current_user,
            original_transaction_id=refund_data.original_transaction_id,
            amount=refund_data.amount,
            idempotency_key=refund_data.idempotency_key,
            description=refund_data.description
        )

        return transaction

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )