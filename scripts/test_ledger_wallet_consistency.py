from decimal import Decimal
from uuid import uuid4

from app.database import SessionLocal
from app.models.account import Account
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry
from app.services.ledger_service import record_ledger_entries


def test_wallet_balance_consistency():
    db = SessionLocal()

    try:
        # Get sender and receiver accounts
        sender = db.query(Account).filter(
            Account.wallet_id == 1
        ).first()

        receiver = db.query(Account).filter(
            Account.wallet_id == 2
        ).first()

        assert sender is not None, "Sender account not found"
        assert receiver is not None, "Receiver account not found"

        # Get corresponding wallets
        sender_wallet = db.query(Wallet).filter(
            Wallet.id == sender.wallet_id
        ).first()

        receiver_wallet = db.query(Wallet).filter(
            Wallet.id == receiver.wallet_id
        ).first()

        assert sender_wallet is not None, "Sender wallet not found"
        assert receiver_wallet is not None, "Receiver wallet not found"

        # Set matching temporary balances
        sender.balance = Decimal("1000.00")
        sender_wallet.balance = Decimal("1000.00")

        receiver.balance = Decimal("100.00")
        receiver_wallet.balance = Decimal("100.00")

        db.flush()

        # Create a pending transaction
        transaction = Transaction(
            transaction_ref=f"TEST-{uuid4().hex[:12].upper()}",
            type="P2P Transfer",
            amount=Decimal("200.00"),
            status="Pending",
            initiated_by=1,
            description="Wallet consistency test"
        )

        db.add(transaction)
        db.flush()

        # Post ledger entries
        record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=sender,
            credit_account=receiver,
            amount=Decimal("200.00")
        )

        db.flush()

        # Verify account balances
        assert sender.balance == Decimal("800.00")
        assert receiver.balance == Decimal("300.00")

        # Verify wallet balances
        assert sender_wallet.balance == Decimal("800.00")
        assert receiver_wallet.balance == Decimal("300.00")

        # Verify wallet/account consistency
        assert sender_wallet.balance == sender.balance
        assert receiver_wallet.balance == receiver.balance

        print("PASS: Sender wallet matches sender account")
        print("PASS: Receiver wallet matches receiver account")
        print("PASS: Sender balance updated correctly")
        print("PASS: Receiver balance updated correctly")

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    test_wallet_balance_consistency()
    print("WALLET ACCOUNT CONSISTENCY TEST PASSED")