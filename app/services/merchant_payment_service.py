import secrets
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.account import Account
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.otp import OTP

from app.auth.utils import verify_password
from app.services.ledger_service import record_ledger_entries
from app.services.cashback_service import create_pending_cashback


CENT = Decimal("0.01")


def make_merchant_payment(
    db: Session,
    customer: User,
    merchant_code: str,
    amount: Decimal,
    pin: str,
    otp_code: str,
    idempotency_key: str,
    description: str = "Merchant payment"
):
    # 1. Validate payment amount
    try:
        amount = Decimal(str(amount))

        if not amount.is_finite() or amount <= 0:
            raise ValueError("Amount must be positive")

        if amount != amount.quantize(CENT):
            raise ValueError(
                "Amount cannot have more than two decimal places"
            )

        amount = amount.quantize(CENT)

    except (InvalidOperation, TypeError):
        raise ValueError("Invalid payment amount")

    try:
        # 2. Validate idempotency key
        if not idempotency_key or not idempotency_key.strip():
            raise ValueError("Idempotency key is required")

        existing = db.query(Transaction).filter(
            Transaction.initiated_by == customer.id,
            Transaction.idempotency_key == idempotency_key
        ).first()

        if existing:
            raise ValueError(
                "Idempotency key already used. Use a new key."
            )

        # 3. Find and lock customer wallet
        wallet = (
            db.query(Wallet)
            .filter(Wallet.owner_id == customer.id)
            .with_for_update()
            .first()
        )

        if not wallet:
            raise ValueError("Customer wallet not found")

        if wallet.status != "Active":
            raise ValueError("Customer wallet is not active")

        # 4. Validate customer PIN
        if not wallet.pin_hash:
            raise ValueError("Please set your wallet PIN first")

        if wallet.pin_locked_until:
            if wallet.pin_locked_until > datetime.utcnow():
                raise ValueError("Wallet PIN is temporarily locked")

        if not verify_password(pin, wallet.pin_hash):
            wallet.failed_pin_attempts += 1

            if wallet.failed_pin_attempts >= 3:
                wallet.pin_locked_until = (
                    datetime.utcnow() + timedelta(minutes=5)
                )

            db.commit()
            raise ValueError("Invalid wallet PIN")

        # 5. Find and validate merchant
        merchant = db.query(Merchant).filter(
            Merchant.merchant_code == merchant_code
        ).first()

        if not merchant:
            raise ValueError("Merchant not found")

        if not merchant.is_verified:
            raise ValueError("Merchant is not verified")

        merchant_user = db.query(User).filter(
            User.id == merchant.user_id
        ).first()

        if not merchant_user or not merchant_user.is_active:
            raise ValueError("Merchant account is inactive")

        if merchant_user.role != "Merchant":
            raise ValueError("Invalid merchant account")

        # 6. Find and lock merchant wallet
        merchant_wallet = (
            db.query(Wallet)
            .filter(Wallet.owner_id == merchant.user_id)
            .with_for_update()
            .first()
        )

        if not merchant_wallet:
            raise ValueError("Merchant wallet not found")

        if merchant_wallet.status != "Active":
            raise ValueError("Merchant wallet is not active")

        if wallet.id == merchant_wallet.id:
            raise ValueError("Cannot pay your own merchant account")

        # 7. Check customer balance
        if Decimal(str(wallet.balance)) < amount:
            raise ValueError("Insufficient wallet balance")

        # 8. Find and lock OTP
        otp_record = (
            db.query(OTP)
            .filter(
                OTP.user_id == customer.id,
                OTP.purpose == "wallet_transaction",
                OTP.is_used.is_(False)
            )
            .order_by(OTP.created_at.desc())
            .with_for_update()
            .first()
        )

        if not otp_record:
            raise ValueError("Valid transaction OTP not found")

        if otp_record.expires_at < datetime.utcnow():
            raise ValueError("OTP has expired")

        if otp_record.attempts >= 3:
            raise ValueError("OTP attempts exceeded")

        if not verify_password(otp_code, otp_record.otp_hash):
            otp_record.attempts += 1
            db.commit()
            raise ValueError("Invalid OTP")

        # 9. Find both ledger accounts
        customer_account = db.query(Account).filter(
            Account.wallet_id == wallet.id,
            Account.account_type == "User Wallet"
        ).first()

        merchant_account = db.query(Account).filter(
            Account.wallet_id == merchant_wallet.id,
            Account.account_type == "Merchant Wallet"
        ).first()

        if not customer_account or not merchant_account:
            raise ValueError(
                "Customer or merchant ledger account not found"
            )

        # 10. Create merchant payment transaction
        transaction = Transaction(
            transaction_ref=f"MER-{secrets.token_hex(8).upper()}",
            type="Merchant Payment",
            amount=amount,
            status="Pending",
            initiated_by=customer.id,
            idempotency_key=idempotency_key,
            description=description
        )

        db.add(transaction)
        db.flush()

        # 11. Record double-entry ledger entries
        record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=customer_account,
            credit_account=merchant_account,
            amount=amount
        )

        # 12. Create pending cashback
        # The ledger service marks the payment as Success.
        create_pending_cashback(
            db=db,
            transaction=transaction
        )

        # 13. Consume OTP and reset PIN failure count
        otp_record.is_used = True
        wallet.failed_pin_attempts = 0
        wallet.pin_locked_until = None

        # 14. Commit payment, ledger and cashback together
        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise