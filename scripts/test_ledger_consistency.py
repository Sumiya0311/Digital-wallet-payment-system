from decimal import Decimal
from uuid import uuid4

from app.database import SessionLocal
from app.models.account import Account
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry
from app.services.ledger_service import record_ledger_entries


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

    assert sender_wallet is not None
    assert receiver_wallet is not None

    # 3. Set temporary test balances
    sender.balance = Decimal("1000.00")
    receiver.balance = Decimal("100.00")

    sender_wallet.balance = Decimal("1000.00")
    receiver_wallet.balance = Decimal("100.00")

    db.flush()

    # 4. Create a temporary successful transaction
    transaction = Transaction(
        transaction_ref=f"TEST-{uuid4().hex[:12].upper()}",
        type="P2P Transfer",
        amount=Decimal("200.00"),
        status="Pending",
        initiated_by=1,
        description="Ledger consistency test"
    )

    db.add(transaction)
    db.flush()

    # 5. Post double-entry ledger
    record_ledger_entries(
        db=db,
        transaction=transaction,
        debit_account=sender,
        credit_account=receiver,
        amount=Decimal("200.00")
    )

    db.flush()

    # 6. Read ledger entries from database
    entries = db.query(LedgerEntry).filter(
        LedgerEntry.transaction_id == transaction.id
    ).all()

    assert len(entries) == 2, "Exactly two entries required"

    debit_entries = [
        entry for entry in entries
        if entry.entry_type == "Debit"
    ]

    credit_entries = [
        entry for entry in entries
        if entry.entry_type == "Credit"
    ]

    assert len(debit_entries) == 1
    assert len(credit_entries) == 1

    # 7. Verify equal amounts
    debit_amount = Decimal(str(debit_entries[0].amount))
    credit_amount = Decimal(str(credit_entries[0].amount))

    assert debit_amount == credit_amount
    assert debit_amount == transaction.amount

    # 8. Verify different accounts
    assert (
        debit_entries[0].account_id
        != credit_entries[0].account_id
    )

    # 9. Verify transaction status
    assert transaction.status == "Success"

    print("PASS: Exactly two ledger entries created")
    print("PASS: One Debit entry and one Credit entry")
    print("PASS: Debit and Credit amounts are equal")
    print("PASS: Both entries belong to different accounts")
    print("PASS: Transaction marked as Success")

    print("LEDGER CONSISTENCY TEST PASSED")

finally:
    # Restore all temporary database changes
    db.rollback()
    db.close()