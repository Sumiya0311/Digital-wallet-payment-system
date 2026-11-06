import secrets
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry

from app.services.ledger_service import record_ledger_entries


CENT = Decimal("0.01")


def process_withdrawal_reversal(
    db: Session,
    admin: User,
    original_transaction_id: int,
    idempotency_key: str,
    description: str = "Withdrawal reversal"
):
    try:
        # 1. Only Admin can process withdrawal reversals
        if admin.role != "Admin":
            raise ValueError(
                "Only administrators can process withdrawal reversals"
            )

        # 2. Check idempotency
        existing = db.query(Transaction).filter(
            Transaction.initiated_by == admin.id,
            Transaction.idempotency_key == idempotency_key
        ).first()

        if existing:
            raise ValueError(
                "Idempotency key already used. Use a new key."
            )

        # 3. Lock original withdrawal
        original = (
            db.query(Transaction)
            .filter(Transaction.id == original_transaction_id)
            .with_for_update()
            .first()
        )

        if not original:
            raise ValueError("Original transaction not found")

        if original.type != "Withdrawal":
            raise ValueError(
                "Original transaction is not a withdrawal"
            )

        if original.status != "Success":
            raise ValueError(
                "Only successful withdrawals can be reversed"
            )

        # 4. Check if already reversed
        existing_reversal = db.query(Transaction).filter(
            Transaction.original_transaction_id == original.id,
            Transaction.type == "Withdrawal Reversal",
            Transaction.status == "Success"
        ).first()

        if existing_reversal:
            raise ValueError(
                "This withdrawal has already been reversed"
            )

        # 5. Find original customer
        customer = db.query(User).filter(
            User.id == original.initiated_by
        ).first()

        if not customer or not customer.is_active:
            raise ValueError(
                "Original customer account is unavailable"
            )

        # 6. Find customer wallet
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

        # 7. Find ledger accounts
        bank_account = db.query(Account).filter(
            Account.account_type == "Bank Settlement"
        ).first()

        user_account = db.query(Account).filter(
            Account.wallet_id == wallet.id,
            Account.account_type == "User Wallet"
        ).first()

        if not bank_account or not user_account:
            raise ValueError("Required ledger accounts not found")

        # 8. Verify original withdrawal debit
        original_debit = db.query(LedgerEntry).filter(
            LedgerEntry.transaction_id == original.id,
            LedgerEntry.account_id == user_account.id,
            LedgerEntry.entry_type == "Debit"
        ).first()

        if not original_debit:
            raise ValueError(
                "Original withdrawal ledger entry not found"
            )

        if Decimal(str(original_debit.amount)).quantize(CENT) != Decimal(
            str(original.amount)
        ).quantize(CENT):
            raise ValueError(
                "Original withdrawal ledger amount does not match"
            )

        # 9. Create reversal transaction
        reversal = Transaction(
            transaction_ref=f"WDR-{secrets.token_hex(8).upper()}",
            type="Withdrawal Reversal",
            amount=original.amount,
            status="Pending",
            initiated_by=admin.id,
            original_transaction_id=original.id,
            idempotency_key=idempotency_key,
            description=description
        )

        db.add(reversal)
        db.flush()

        # 10. Reverse the original ledger movement
        # Debit Bank Settlement; Credit User Wallet
        record_ledger_entries(
            db=db,
            transaction=reversal,
            debit_account=bank_account,
            credit_account=user_account,
            amount=original.amount
        )

        db.commit()
        db.refresh(reversal)

        return reversal

    except Exception:
        db.rollback()
        raise