from decimal import Decimal

from app.database import SessionLocal
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry
from app.services.ledger_service import record_ledger_entries


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

    sender_balance_before = sender.balance
    receiver_balance_before = receiver.balance

    # Request an amount greater than the sender's balance.
    amount = Decimal(str(sender.balance)) + Decimal("1.00")

    transaction = Transaction(
        transaction_ref="TEST-NEGATIVE-BALANCE-001",
        type="P2P Transfer",
        amount=amount,
        status="Pending",
        initiated_by=1,
        description="Negative balance protection test"
    )

    db.add(transaction)
    db.flush()

    try:
        record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=sender,
            credit_account=receiver,
            amount=amount
        )

        raise AssertionError(
            "ERROR: Insufficient balance was not rejected"
        )

    except ValueError as exc:
        assert "Insufficient" in str(exc)

        db.rollback()

        print("PASS: Insufficient balance rejected correctly")

    sender_after = db.query(Account).filter(
        Account.id == sender.id
    ).first()

    receiver_after = db.query(Account).filter(
        Account.id == receiver.id
    ).first()

    assert sender_after.balance == sender_balance_before
    print("PASS: Sender balance unchanged")

    assert receiver_after.balance == receiver_balance_before
    print("PASS: Receiver balance unchanged")

    entries = db.query(LedgerEntry).filter(
        LedgerEntry.transaction_id == transaction.id
    ).count()

    assert entries == 0
    print("PASS: No ledger entries created")

    print("NEGATIVE BALANCE TEST PASSED")

finally:
    db.rollback()
    db.close()