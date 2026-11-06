import secrets
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.utils import verify_password
from app.models.account import Account
from app.models.bank_account import BankAccount
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.models.withdrawal import Withdrawal
from app.services.ledger_service import record_ledger_entries


CENT = Decimal("0.01")
MIN_WITHDRAWAL = Decimal("100.00")
DAILY_LIMIT = Decimal("25000.00")
MONTHLY_LIMIT = Decimal("100000.00")


def process_withdrawal(
    db: Session,
    customer: User,
    bank_account_id: int,
    amount: Decimal,
    pin: str,
    idempotency_key: str,
    description: str = "Wallet withdrawal"
):
    try:
        amount = Decimal(str(amount))

        if not amount.is_finite():
            raise ValueError("Invalid withdrawal amount")

        if amount < MIN_WITHDRAWAL:
            raise ValueError("Minimum withdrawal amount is Rs.100")

        if amount != amount.quantize(CENT):
            raise ValueError(
                "Withdrawal amount cannot have more than two decimal places"
            )

        amount = amount.quantize(CENT)

    except (InvalidOperation, TypeError):
        raise ValueError("Invalid withdrawal amount")

    try:
        if customer.role not in ("User", "Merchant"):
            raise ValueError(
                "Only users and merchants can withdraw"
            )

        if not idempotency_key or len(idempotency_key) < 10:
            raise ValueError("Invalid idempotency key")

        # Check duplicate request
        existing = (
            db.query(Transaction)
            .filter(
                Transaction.initiated_by == customer.id,
                Transaction.idempotency_key == idempotency_key
            )
            .first()
        )

        if existing:
            raise ValueError(
                "Idempotency key already used. Use a new key."
            )

        # Lock wallet
        wallet = (
            db.query(Wallet)
            .filter(Wallet.owner_id == customer.id)
            .with_for_update()
            .first()
        )

        if not wallet:
            raise ValueError("Wallet not found")

        if wallet.status != "Active":
            raise ValueError("Wallet is not active")

        if customer.role == "User" and wallet.kyc_level != "Full":
            raise ValueError(
                "Full KYC is required for withdrawals"
            )

        # Validate destination bank account
        destination = (
            db.query(BankAccount)
            .filter(
                BankAccount.id == bank_account_id,
                BankAccount.user_id == customer.id,
                BankAccount.is_active.is_(True)
            )
            .first()
        )

        if not destination:
            raise ValueError(
                "Active bank account not found for this user"
            )

        # Validate wallet PIN
        if not wallet.pin_hash:
            raise ValueError("Please set your wallet PIN first")

        now = datetime.utcnow()

        if wallet.pin_locked_until and wallet.pin_locked_until > now:
            raise ValueError("Wallet PIN is temporarily locked")

        if not verify_password(pin, wallet.pin_hash):
            wallet.failed_pin_attempts = (
                wallet.failed_pin_attempts or 0
            ) + 1

            if wallet.failed_pin_attempts >= 3:
                wallet.pin_locked_until = (
                    now + timedelta(minutes=30)
                )

            db.commit()
            raise ValueError("Invalid wallet PIN")

        wallet.failed_pin_attempts = 0
        wallet.pin_locked_until = None

        # Verify balance
        if Decimal(str(wallet.balance)) < amount:
            raise ValueError("Insufficient wallet balance")

        # Combined outgoing limits for Full KYC users
        if customer.role == "User":
            day_start = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            month_start = day_start.replace(day=1)

            outgoing_types = (
                "P2P Transfer",
                "Merchant Payment",
                "Withdrawal"
            )

            def outgoing_total(start_date):
                result = (
                    db.query(func.coalesce(
                        func.sum(Transaction.amount), 0
                    ))
                    .filter(
                        Transaction.initiated_by == customer.id,
                        Transaction.type.in_(outgoing_types),
                        Transaction.status.in_(
                            ("Success", "Pending", "On Hold")
                        ),
                        Transaction.original_transaction_id.is_(None),
                        Transaction.created_at >= start_date
                    )
                    .scalar()
                )
                return Decimal(str(result))

            if outgoing_total(day_start) + amount > DAILY_LIMIT:
                raise ValueError(
                    "Daily outgoing limit of Rs.25000 exceeded"
                )

            if outgoing_total(month_start) + amount > MONTHLY_LIMIT:
                raise ValueError(
                    "Monthly outgoing limit of Rs.100000 exceeded"
                )

        # Find ledger accounts
        user_account = (
            db.query(Account)
            .filter(
                Account.wallet_id == wallet.id,
                Account.account_type.in_(
                    ("User Wallet", "Merchant Wallet")
                )
            )
            .first()
        )

        clearing_account = (
            db.query(Account)
            .filter(
                Account.account_type == "Withdrawal Clearing"
            )
            .first()
        )

        if not user_account:
            raise ValueError("Wallet ledger account not found")

        if not clearing_account:
            raise ValueError(
                "Withdrawal Clearing account not found"
            )

        # Create pending transaction
        transaction = Transaction(
            transaction_ref=(
                f"WD-{secrets.token_hex(8).upper()}"
            ),
            type="Withdrawal",
            amount=amount,
            status="Pending",
            initiated_by=customer.id,
            idempotency_key=idempotency_key,
            description=description
        )

        db.add(transaction)
        db.flush()

        # Debit User Wallet; Credit Withdrawal Clearing
        record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=user_account,
            credit_account=clearing_account,
            amount=amount,
            final_status="Pending"
        )

        # Create withdrawal record
        withdrawal = Withdrawal(
            transaction_id=transaction.id,
            user_id=customer.id,
            bank_account_id=destination.id,
            amount=amount,
            status="Pending"
        )

        db.add(withdrawal)

        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise