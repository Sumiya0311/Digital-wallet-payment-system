from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.otp import OTP

from app.auth.utils import verify_password
from app.utils.otp_utils import verify_otp

from app.services.ledger_service import record_ledger_entries
from app.services.fraud_detection_service import detect_fraud
from app.services.transaction_limit_service import validate_outgoing_limits


CENT = Decimal("0.01")
OTP_THRESHOLD = Decimal("5000.00")
PIN_LOCK_MINUTES = 30


def execute_p2p_transfer(
    db: Session,
    sender: User,
    receiver_wallet_number: str,
    amount: Decimal,
    pin: str,
    otp: str | None,
    idempotency_key: str,
    description: str | None = None
):
    # 1. Validate transfer amount
    try:
        amount = Decimal(str(amount))

        if not amount.is_finite() or amount <= 0:
            raise ValueError(
                "Transfer amount must be positive"
            )

        if amount != amount.quantize(CENT):
            raise ValueError(
                "Amount cannot have more than two decimal places"
            )

        amount = amount.quantize(CENT)

    except (InvalidOperation, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("Invalid transfer amount") from exc

    # 2. Validate idempotency key
    if not idempotency_key or not idempotency_key.strip():
        raise ValueError("Idempotency key is required")

    # 3. Check for an existing transaction
    existing_transaction = (
        db.query(Transaction)
        .filter(
            Transaction.initiated_by == sender.id,
            Transaction.idempotency_key == idempotency_key
        )
        .first()
    )

    if existing_transaction:
        return existing_transaction

    # 4. Lock sender wallet
    sender_wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == sender.id)
        .with_for_update()
        .first()
    )

    if not sender_wallet:
        raise ValueError("Sender wallet not found")

    if sender_wallet.status != "Active":
        raise ValueError("Sender wallet is not active")

    if not sender_wallet.pin_hash:
        raise ValueError(
            "Please set your wallet PIN first"
        )

    now = datetime.utcnow()

    # 5. Check PIN lock
    if sender_wallet.pin_locked_until:
        if now < sender_wallet.pin_locked_until:
            raise ValueError(
                "Wallet PIN is temporarily locked"
            )

        sender_wallet.pin_locked_until = None
        sender_wallet.failed_pin_attempts = 0

    # 6. Verify wallet PIN
    if not verify_password(
        pin,
        sender_wallet.pin_hash
    ):
        sender_wallet.failed_pin_attempts = (
            sender_wallet.failed_pin_attempts or 0
        ) + 1

        if sender_wallet.failed_pin_attempts >= 3:
            sender_wallet.pin_locked_until = (
                now + timedelta(
                    minutes=PIN_LOCK_MINUTES
                )
            )

        db.commit()

        raise ValueError("Invalid wallet PIN")

    sender_wallet.failed_pin_attempts = 0
    sender_wallet.pin_locked_until = None

    # 7. Verify OTP for transfers above Rs.5000
    otp_record = None

    if amount > OTP_THRESHOLD:
        if not otp:
            raise ValueError(
                "OTP is required for transfers above Rs.5000"
            )

        otp_record = (
            db.query(OTP)
            .filter(
                OTP.user_id == sender.id,
                OTP.purpose == "wallet_transaction",
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
                "No active transaction OTP found"
            )

        if otp_record.expires_at <= now:
            raise ValueError("OTP has expired")

        if otp_record.attempts >= 3:
            raise ValueError(
                "Maximum OTP attempts exceeded"
            )

        if not verify_otp(
            otp,
            otp_record.otp_hash
        ):
            otp_record.attempts += 1
            db.commit()

            raise ValueError("Invalid OTP")

    # 8. Find receiver wallet
    receiver_wallet = (
        db.query(Wallet)
        .filter(
            Wallet.wallet_number == receiver_wallet_number
        )
        .with_for_update()
        .first()
    )

    if not receiver_wallet:
        raise ValueError("Receiver wallet not found")

    if receiver_wallet.id == sender_wallet.id:
        raise ValueError(
            "Cannot transfer money to your own wallet"
        )

    if receiver_wallet.status != "Active":
        raise ValueError(
            "Receiver wallet is not active"
        )

    receiver_user = (
        db.query(User)
        .filter(
            User.id == receiver_wallet.owner_id
        )
        .first()
    )

    if not receiver_user or not receiver_user.is_active:
        raise ValueError(
            "Receiver account is inactive"
        )

    # 9. Validate combined daily/monthly KYC limits
    validate_outgoing_limits(
        db=db,
        wallet=sender_wallet,
        amount=amount
    )

    # 10. Verify available balance
    sender_balance = Decimal(
        str(sender_wallet.balance)
    )

    if sender_balance < amount:
        raise ValueError(
            "Insufficient wallet balance"
        )

    # 11. Find corresponding ledger accounts
    sender_account = (
        db.query(Account)
        .filter(
            Account.wallet_id == sender_wallet.id,
            Account.account_type == "User Wallet"
        )
        .with_for_update()
        .first()
    )

    receiver_account = (
        db.query(Account)
        .filter(
            Account.wallet_id == receiver_wallet.id,
            Account.account_type == "User Wallet"
        )
        .with_for_update()
        .first()
    )

    if not sender_account or not receiver_account:
        raise ValueError(
            "Wallet ledger account not found"
        )

    if Decimal(str(sender_account.balance)) != sender_balance:
        raise ValueError(
            "Sender wallet and ledger balances do not match"
        )

    # 12. Create pending transaction
    transaction = Transaction(
        transaction_ref=(
            f"P2P-{uuid4().hex[:16].upper()}"
        ),
        type="P2P Transfer",
        amount=amount,
        status="Pending",
        initiated_by=sender.id,
        receiver_wallet_id=receiver_wallet.id,
        idempotency_key=idempotency_key,
        description=(
            description or "P2P wallet transfer"
        )
    )

    db.add(transaction)
    db.flush()

    # 13. Detect fraud BEFORE posting ledger entries
    fraud_flag = detect_fraud(
        db=db,
        transaction=transaction
    )

    if fraud_flag is not None:
        # Held transactions do not move money.
        # Approval must revalidate funds and limits.
        if otp_record is not None:
            otp_record.is_used = True

        db.commit()
        db.refresh(transaction)

        return transaction

    # 14. Post double-entry ledger records
    record_ledger_entries(
        db=db,
        transaction=transaction,
        debit_account=sender_account,
        credit_account=receiver_account,
        amount=amount
    )

    # 15. Consume OTP after successful processing
    if otp_record is not None:
        otp_record.is_used = True

    # 16. Commit transaction
    db.commit()
    db.refresh(transaction)

    return transaction