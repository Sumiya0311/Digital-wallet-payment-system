from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.models.kyc import KYC

from app.schemas.kyc import (
    KYCSubmitRequest,
    KYCRejectRequest,
    KYCResponse
)

from app.auth.dependencies import (
    get_current_user,
    get_current_admin
)


router = APIRouter(tags=["KYC"])


# 1. Submit KYC
@router.post(
    "/kyc",
    response_model=KYCResponse,
    status_code=status.HTTP_201_CREATED
)
def submit_kyc(
    request: KYCSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ("User", "Merchant"):
        raise HTTPException(
            status_code=403,
            detail="Only users and merchants can submit KYC"
        )

    existing = db.query(KYC).filter(
        KYC.user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="KYC application already exists"
        )

    kyc = KYC(
        user_id=current_user.id,
        pan_number=request.pan_number,
        aadhaar_last4=request.aadhaar_last4,
        full_name=request.full_name.strip(),
        date_of_birth=request.date_of_birth,
        status="Pending"
    )

    try:
        db.add(kyc)
        db.commit()
        db.refresh(kyc)
        return kyc

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="KYC already exists or PAN is registered"
        )


# 2. View my KYC
@router.get(
    "/kyc",
    response_model=KYCResponse
)
def get_my_kyc(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    kyc = db.query(KYC).filter(
        KYC.user_id == current_user.id
    ).first()

    if not kyc:
        raise HTTPException(
            status_code=404,
            detail="KYC application not found"
        )

    return kyc


# 3. Admin approves KYC
@router.put(
    "/admin/kyc/{kyc_id}/approve",
    response_model=KYCResponse
)
def approve_kyc(
    kyc_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    try:
        kyc = (
            db.query(KYC)
            .filter(KYC.id == kyc_id)
            .with_for_update()
            .first()
        )

        if not kyc:
            raise HTTPException(
                status_code=404,
                detail="KYC application not found"
            )

        if kyc.status != "Pending":
            raise HTTPException(
                status_code=409,
                detail="Only pending KYC applications can be approved"
            )

        wallet = (
            db.query(Wallet)
            .filter(Wallet.owner_id == kyc.user_id)
            .with_for_update()
            .first()
        )

        if not wallet:
            raise HTTPException(
                status_code=404,
                detail="User wallet not found"
            )

        kyc.status = "Approved"
        kyc.rejection_reason = None
        wallet.kyc_level = "Full"

        db.commit()
        db.refresh(kyc)

        return kyc

    except Exception:
        db.rollback()
        raise


# 4. Admin rejects KYC
@router.put(
    "/admin/kyc/{kyc_id}/reject",
    response_model=KYCResponse
)
def reject_kyc(
    kyc_id: int,
    request: KYCRejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    try:
        kyc = (
            db.query(KYC)
            .filter(KYC.id == kyc_id)
            .with_for_update()
            .first()
        )

        if not kyc:
            raise HTTPException(
                status_code=404,
                detail="KYC application not found"
            )

        if kyc.status != "Pending":
            raise HTTPException(
                status_code=409,
                detail="Only pending KYC applications can be rejected"
            )

        kyc.status = "Rejected"
        kyc.rejection_reason = request.rejection_reason.strip()

        db.commit()
        db.refresh(kyc)

        return kyc

    except Exception:
        db.rollback()
        raise