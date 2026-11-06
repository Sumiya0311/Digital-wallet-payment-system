from decimal import Decimal
from uuid import uuid4

from app.database import SessionLocal
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.services.ledger_service import record_ledger_entries


OPENING_AMOUNT = Decimal("1000.00")
IDEMPOTENCY_KEY = "DEV-OPENING-BALANCE-2026-001"


def create_opening_balance():
    db = SessionLocal()

    try:
        
        admin = (
            db.query(User)
            .filter(
                User.is_active.is_(True)) 
                .order_by(User.id)
                .first()
            
        )

        if not admin:
            raise ValueError("No active user found")

        # Prevent duplicate execution.
        existing = (
            db.query(Transaction)
            .filter(
                Transaction.initiated_by == admin.id,
                Transaction.idempotency_key == IDEMPOTENCY_KEY
            )
            .first()
        )

        if existing:
            raise ValueError(
                "Opening balance transaction already exists. "
                "No additional funding was created."
            )

        
        bank_account = (
            db.query(Account)
            .filter(
                Account.account_type == "Bank Settlement",
                Account.wallet_id.is_(None)
            )
            .with_for_update()
            .first()
        )

        equity_account = (
            db.query(Account)
            .filter(
                Account.account_type == "Opening Equity",
                Account.wallet_id.is_(None)
            )
            .with_for_update()
            .first()
        )

        if not bank_account or not equity_account:
            raise ValueError("Required system accounts not found")

        if (
            Decimal(str(bank_account.balance)) != Decimal("0.00")
            or Decimal(str(equity_account.balance)) != Decimal("0.00")
        ):
            raise ValueError(
                "System account balances are not zero. "
                "Review them before creating opening funding."
            )

        
        transaction = Transaction(
            transaction_ref=f"OPEN-{uuid4().hex[:16].upper()}",
            type="Opening Balance",
            amount=OPENING_AMOUNT,
            status="Pending",
            initiated_by=admin.id,
            idempotency_key=IDEMPOTENCY_KEY,
            description="Simulated development opening funds"
        )

        db.add(transaction)
        db.flush()

        # Debit Bank Settlement and credit Opening Equity.
        record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=bank_account,
            credit_account=equity_account,
            amount=OPENING_AMOUNT
        )

        db.commit()
        db.refresh(transaction)

        print("Opening balance transaction created successfully.")
        print("Transaction reference:", transaction.transaction_ref)
        print("Amount:", transaction.amount)
        print("Status:", transaction.status)
        print("Bank Settlement balance:", bank_account.balance)
        print("Opening Equity balance:", equity_account.balance)
        print("This is simulated development funding, not real money.")

    except Exception as exc:
        db.rollback()
        print("Opening balance creation failed:", str(exc))
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_opening_balance()