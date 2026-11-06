from decimal import Decimal
from secrets import token_hex

from app.database import SessionLocal
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry
from app.services.ledger_service import record_ledger_entries


db = SessionLocal()

try:
    # Find the two test wallet accounts
    sender_account = (
        db.query(Account)
        .filter(Account.wallet_id == 1)
        .first()
    )

    receiver_account = (
        db.query(Account)
        .filter(Account.wallet_id == 2)
        .first()
    )

    if not sender_account or not receiver_account:
        raise RuntimeError("Test wallet accounts not found")

    print("Sender balance:", sender_account.balance)
    print("Receiver balance:", receiver_account.balance)

    # Create a temporary pending transaction
    transaction = Transaction(
        transaction_ref=f"TEST-{token_hex(12).upper()}",
        type="P2P Transfer",
        amount=Decimal("10.00"),
        status="Pending",
        initiated_by=1,
        description="Insufficient funds test"
    )

    db.add(transaction)
    db.flush()

    transaction_id = transaction.id

    try:
        record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=sender_account,
            credit_account=receiver_account,
            amount=Decimal("10.00")
        )

        raise AssertionError(
            "Test failed: transaction should have been rejected"
        )

    except ValueError as exc:
        if str(exc) != "Insufficient account balance":
            raise

        print("PASS: Insufficient funds rejected correctly")

    # Roll back the temporary transaction
    db.rollback()

    # Verify that balances remain unchanged
    sender_balance = (
        db.query(Account)
        .filter(Account.wallet_id == 1)
        .first()
        .balance
    )

    receiver_balance = (
        db.query(Account)
        .filter(Account.wallet_id == 2)
        .first()
        .balance
    )

    ledger_count = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.transaction_id == transaction_id)
        .count()
    )

    assert sender_balance == Decimal("0.00")
    assert receiver_balance == Decimal("0.00")
    assert ledger_count == 0

    print("PASS: Sender balance unchanged")
    print("PASS: Receiver balance unchanged")
    print("PASS: No ledger entries were created")
    print("LEDGER INSUFFICIENT FUNDS TEST PASSED")

except Exception:
    db.rollback()
    raise

finally:
    db.close()