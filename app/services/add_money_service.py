from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.wallet import Wallet
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User

from app.services.ledger_service import record_ledger_entries


CENT = Decimal("0.01")


def execute_add_money(
    db: Session,
    user: User,
    amount: Decimal,
    idempotency_key: str,
    description: str = "Test wallet top-up"
):
    amount = Decimal(str(amount))

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be positive")

    if amount != amount.quantize(CENT):
        raise ValueError("Amount cannot have more than two decimal places")

    amount = amount.quantize(CENT)

    # Lock the user's wallet
    wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == user.id)
        .with_for_update()
        .first()
    )

    if not wallet:
        raise ValueError("Wallet not found")

    if wallet.status != "Active":
        raise ValueError("Wallet is not active")

    # Check idempotency
    existing = (
        db.query(Transaction)
        .filter(
            Transaction.initiated_by == user.id,
            Transaction.idempotency_key == idempotency_key
        )
        .first()
    )

    if existing:
        return existing

    # Find the user's ledger account
    user_account = (
        db.query(Account)
        .filter(
            Account.wallet_id == wallet.id,
            Account.account_type == "User Wallet"
        )
        .first()
    )

    # Find Bank Settlement account
    bank_account = (
        db.query(Account)
        .filter(
            Account.account_type == "Bank Settlement",
            Account.wallet_id.is_(None)
        )
        .first()
    )

    if not user_account or not bank_account:
        raise ValueError("Required ledger accounts not found")

    transaction = Transaction(
        transaction_ref=f"ADD-{uuid4().hex[:16].upper()}",
        type="Add Money",
        amount=amount,
        status="Pending",
        initiated_by=user.id,
        idempotency_key=idempotency_key,
        description=description
    )

    db.add(transaction)
    db.flush()

    # Bank Settlement is debited.
    # User Wallet is credited.
    record_ledger_entries(
        db=db,
        transaction=transaction,
        debit_account=bank_account,
        credit_account=user_account,
        amount=amount
    )

    db.commit()
    db.refresh(transaction)

    return transaction