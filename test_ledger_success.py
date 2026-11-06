from decimal import Decimal
from uuid import uuid4

from app.database import SessionLocal
from app.models.account import Account
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry
from app.services.ledger_service import record_ledger_entries


def test_successful_ledger_transfer():
    db = SessionLocal()

    try:
        # 1. Get sender and receiver accounts
        sender = db.query(Account).filter(
            Account.wallet_id == 1
        ).first()

        receiver = db.query(Account).filter(
            Account.wallet_id == 2
        ).first()

        assert sender is not None, "Sender account not found"
        assert receiver is not None, "Receiver account not found"

        # 2. Get corresponding wallets
        sender_wallet = db.query(Wallet).filter(
            Wallet.id == sender.wallet_id
        ).first()

        receiver_wallet = db.query(Wallet).filter(
            Wallet.id == receiver.wallet_id
        ).first()

        assert sender_wallet is not None, "Sender wallet not found"
        assert receiver_wallet is not None, "Receiver wallet not found"

        # 3. Set temporary test balances
        sender.balance = Decimal("1000.00")
        receiver.balance = Decimal("100.00")

        sender_wallet.balance = Decimal("1000.00")
        receiver_wallet.balance = Decimal("100.00")

        db.flush()

        # 4. Create pending transaction
        transaction = Transaction(
            transaction_ref=f"TEST-{uuid4().hex[:12].upper()}",
            type="P2P Transfer",
            amount=Decimal("200.00"),
            status="Pending",
            initiated_by=1,
            description="Successful ledger transfer test"
        )

        db.add(transaction)
        db.flush()

        # 5. Record double-entry ledger
        debit_entry, credit_entry = record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=sender,
            credit_account=receiver,
            amount=Decimal("200.00")
        )

        db.flush()

        # 6. Verify account balances
        assert sender.balance == Decimal("800.00")
        assert receiver.balance == Decimal("300.00")

        # 7. Verify wallet balances
        assert sender_wallet.balance == Decimal("800.00")
        assert receiver_wallet.balance == Decimal("300.00")

        # 8. Verify ledger entries
        assert debit_entry.entry_type == "Debit"
        assert credit_entry.entry_type == "Credit"

        assert debit_entry.amount == Decimal("200.00")
        assert credit_entry.amount == Decimal("200.00")

        # 9. Verify transaction status
        assert transaction.status == "Success"

        # 10. Verify exactly two ledger entries
        entry_count = db.query(LedgerEntry).filter(
            LedgerEntry.transaction_id == transaction.id
        ).count()

        assert entry_count == 2

        print("PASS: Sender debited correctly")
        print("PASS: Receiver credited correctly")
        print("PASS: Sender wallet synchronized")
        print("PASS: Receiver wallet synchronized")
        print("PASS: Debit and credit entries created")
        print("PASS: Transaction marked as Success")

    finally:
        # Roll back all temporary test changes
        db.rollback()
        db.close()


if __name__ == "__main__":
    test_successful_ledger_transfer()
    print("SUCCESSFUL LEDGER TRANSFER TEST PASSED")