from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User

from app.services.ledger_service import record_ledger_entries


def fund_cashback_pool(
    db: Session,
    admin: User,
    amount: Decimal = Decimal("100.00")
):
    amount = Decimal(str(amount))

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Funding amount must be positive")

    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Amount cannot have more than two decimal places")

    amount = amount.quantize(Decimal("0.01"))

    try:
        bank_account = (
            db.query(Account)
            .filter(
                Account.account_type == "Bank Settlement",
                Account.wallet_id.is_(None)
            )
            .first()
        )

        pool_account = (
            db.query(Account)
            .filter(
                Account.account_type == "Cashback Pool",
                Account.wallet_id.is_(None)
            )
            .first()
        )

        if not bank_account:
            raise ValueError("Bank Settlement account not found")

        if not pool_account:
            raise ValueError("Cashback Pool account not found")

        transaction = Transaction(
            transaction_ref=f"CBF-{uuid4().hex[:20].upper()}",
            type="Cashback Pool Funding",
            amount=amount,
            status="Pending",
            initiated_by=admin.id,
            idempotency_key=f"CBF-{uuid4().hex}",
            description="Admin funding of Cashback Pool from Bank Settlement"
        )

        db.add(transaction)
        db.flush()

        entries = record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=pool_account,
            credit_account=bank_account,
            amount=amount
        )

        db.commit()

        db.refresh(transaction)
        db.refresh(bank_account)
        db.refresh(pool_account)

        return {
            "message": "Cashback Pool funded successfully",
            "transaction_id": transaction.id,
            "transaction_ref": transaction.transaction_ref,
            "amount": str(amount),
            "bank_settlement_balance": str(bank_account.balance),
            "cashback_pool_balance": str(pool_account.balance),
            "ledger_entries_created": len(entries)
        }

    except Exception:
        db.rollback()
        raise