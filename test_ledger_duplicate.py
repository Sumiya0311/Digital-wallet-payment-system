from decimal import Decimal
from uuid import uuid4

from app.database import SessionLocal
from app.models.account import Account
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry
from app.services.ledger_service import record_ledger_entries


def test_duplicate_ledger_posting():
    db = SessionLocal()

    try:
        # 1. Get sender and receiver accounts
        sender = db.query(Account).filter(
            Account.wallet_id == 1
        ).first()

        receiver = db.query(Account).filter(
            Account.wallet_id == 2
        ).first()

        assert sender is not None
        assert receiver is not None

        # 2. Get corresponding wallets
        sender_wallet = db.query(Wallet).filter(
            Wallet.id == sender.wallet_id
        ).first()

        receiver_wallet = db.query(Wallet).filter(
            Wallet.id == receiver.wallet_id
        ).first()

        assert sender_wallet is not None
        assert receiver_wallet is not None

        # 3. Set temporary test balances
        sender.balance = Decimal("1000.00")
        receiver.balance = Decimal("100.00")

        sender_wallet.balance = Decimal("1000.00")
        receiver_wallet.balance = Decimal("100.00")

        db.flush()

        # 4. Create one pending transaction
        transaction = Transaction(
            transaction_ref=f"TEST-{uuid4().hex[:12].upper()}",
            type="P2P Transfer",
            amount=Decimal("200.00"),
            status="Pending",
            initiated_by=1,
            description="Duplicate ledger posting test"
        )

        db.add(transaction)
        db.flush()

        # 5. First posting should succeed
        record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=sender,
            credit_account=receiver,
            amount=Decimal("200.00")
        )

        db.flush()

        assert sender.balance == Decimal("800.00")
        assert receiver.balance == Decimal("300.00")

        print("PASS: First ledger posting succeeded")

        # 6. Attempt to post the same transaction again
        try:
            record_ledger_entries(
                db=db,
                transaction=transaction,
                debit_account=sender,
                credit_account=receiver,
                amount=Decimal("200.00")
            )

            raise AssertionError(
                "Duplicate ledger posting was not rejected"
            )

        except ValueError as exc:
            assert str(exc) == (
                "Only pending transactions can be posted"
            )

            print("PASS: Duplicate posting rejected correctly")

        # 7. Verify balances did not change again
        assert sender.balance == Decimal("800.00")
        assert receiver.balance == Decimal("300.00")

        print("PASS: Sender balance unchanged")
        print("PASS: Receiver balance unchanged")

        # 8. Verify exactly two ledger entries exist
        entry_count = db.query(LedgerEntry).filter(
            LedgerEntry.transaction_id == transaction.id
        ).count()

        assert entry_count == 2

        print("PASS: No duplicate ledger entries created")

    finally:
        # Roll back all test data
        db.rollback()
        db.close()


if __name__ == "__main__":
    test_duplicate_ledger_posting()
    print("DUPLICATE LEDGER POSTING TEST PASSED")