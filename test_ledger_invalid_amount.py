from decimal import Decimal
from uuid import uuid4

from app.database import SessionLocal
from app.models.account import Account
from app.models.transaction import Transaction
from app.services.ledger_service import record_ledger_entries


def test_invalid_ledger_amounts():
    db = SessionLocal()

    try:
        
        sender = db.query(Account).filter(
            Account.wallet_id == 1
        ).first()

        receiver = db.query(Account).filter(
            Account.wallet_id == 2
        ).first()

        assert sender is not None, "Sender account not found"
        assert receiver is not None, "Receiver account not found"

        
        transaction = Transaction(
            transaction_ref=f"TEST-{uuid4().hex[:12].upper()}",
            type="P2P Transfer",
            amount=Decimal("100.00"),
            status="Pending",
            initiated_by=1,
            description="Invalid ledger amount test"
        )

        db.add(transaction)
        db.flush()

        
        try:
            record_ledger_entries(
                db=db,
                transaction=transaction,
                debit_account=sender,
                credit_account=receiver,
                amount=Decimal("0.00")
            )

            raise AssertionError("Zero amount was not rejected")

        except ValueError as exc:
            assert str(exc) == "Transaction amount must be positive"
            print("PASS: Zero amount rejected correctly")

        
        try:
            record_ledger_entries(
                db=db,
                transaction=transaction,
                debit_account=sender,
                credit_account=receiver,
                amount=Decimal("-50.00")
            )

            raise AssertionError("Negative amount was not rejected")

        except ValueError as exc:
            assert str(exc) == "Transaction amount must be positive"
            print("PASS: Negative amount rejected correctly")

        
        assert transaction.status == "Pending"
        print("PASS: Transaction status remains Pending")

        
        from app.models.ledger_entry import LedgerEntry

        entry_count = db.query(LedgerEntry).filter(
            LedgerEntry.transaction_id == transaction.id
        ).count()

        assert entry_count == 0
        print("PASS: No ledger entries created")

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    test_invalid_ledger_amounts()
    print("INVALID LEDGER AMOUNT TEST PASSED")