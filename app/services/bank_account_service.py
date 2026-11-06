from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.bank_account import BankAccount
from app.models.otp import OTP
from app.schemas.bank_account import BankAccountCreate
from app.utils.otp_utils import verify_otp


MAX_BANK_ACCOUNTS = 3
MAX_OTP_ATTEMPTS = 3


def register_bank_account(
    db: Session,
    current_user: User,
    bank_data: BankAccountCreate
):
    try:
        # 1. Lock the user to prevent concurrent registrations
        user = (
            db.query(User)
            .filter(User.id == current_user.id)
            .with_for_update()
            .first()
        )

        if not user:
            raise ValueError("User not found")

        if not user.is_active:
            raise ValueError("User account is inactive")

        # 2. Enforce maximum three bank accounts
        account_count = (
            db.query(BankAccount)
            .filter(BankAccount.user_id == user.id)
            .count()
        )

        if account_count >= MAX_BANK_ACCOUNTS:
            raise ValueError(
                "Maximum three bank accounts allowed"
            )

        # 3. Prevent duplicate bank accounts
        existing_account = (
            db.query(BankAccount)
            .filter(
                BankAccount.user_id == user.id,
                BankAccount.account_number == bank_data.account_number
            )
            .first()
        )

        if existing_account:
            raise ValueError(
                "Bank account already registered"
            )

        # 4. Lock the latest unused bank account OTP
        otp_record = (
            db.query(OTP)
            .filter(
                OTP.user_id == user.id,
                OTP.purpose == "bank_account",
                OTP.is_used.is_(False)
            )
            .order_by(
                OTP.created_at.desc(),
                OTP.id.desc()
            )
            .with_for_update()
            .first()
        )

        if not otp_record:
            raise ValueError(
                "No active bank account OTP found"
            )

        if otp_record.expires_at <= datetime.utcnow():
            raise ValueError("OTP has expired")

        if otp_record.attempts >= MAX_OTP_ATTEMPTS:
            raise ValueError(
                "Maximum OTP verification attempts exceeded"
            )

        # 5. Verify OTP
        if not verify_otp(
            bank_data.otp,
            otp_record.otp_hash
        ):
            otp_record.attempts += 1

            # Persist the failed attempt
            db.commit()

            raise ValueError("Invalid OTP")

        # 6. Create bank account
        new_account = BankAccount(
            user_id=user.id,
            account_holder_name=bank_data.account_holder_name.strip(),
            bank_name=bank_data.bank_name.strip(),
            account_number=bank_data.account_number,
            ifsc_code=bank_data.ifsc_code,
            is_active=True
        )

        db.add(new_account)

        # 7. Consume OTP in the same transaction
        otp_record.is_used = True

        db.flush()
        db.commit()
        db.refresh(new_account)

        return new_account

    except ValueError:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise