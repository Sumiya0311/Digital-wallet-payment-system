from uuid import uuid4
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.transaction import Transaction


def test_transaction_idempotency():

    db = SessionLocal()

    try:
        # 1. Create a unique test idempotency key
        test_key = f"IDEM-{uuid4().hex}"

        # 2. Create the first transaction
        first_transaction = Transaction(
            transaction_ref=f"TEST-{uuid4().hex[:12]}",
            type="P2P Transfer",
            amount=Decimal("100.00"),
            status="Pending",
            initiated_by=1,
            idempotency_key=test_key,
            description="Idempotency test"
        )

        db.add(first_transaction)
        db.commit()

        print("PASS: First transaction created successfully")

        # 3. Attempt another transaction with the same key
        duplicate_transaction = Transaction(
            transaction_ref=f"TEST-{uuid4().hex[:12]}",
            type="P2P Transfer",
            amount=Decimal("200.00"),
            status="Pending",
            initiated_by=1,
            idempotency_key=test_key,
            description="Duplicate idempotency test"
        )

        db.add(duplicate_transaction)

        try:
            db.commit()

            raise AssertionError(
                "Duplicate idempotency key was accepted"
            )

        except IntegrityError:
            db.rollback()
            print("PASS: Duplicate idempotency key rejected")

        # 4. Verify only one transaction exists for this key
        count = db.query(Transaction).filter(
            Transaction.initiated_by == 1,
            Transaction.idempotency_key == test_key
        ).count()

        assert count == 1

        print("PASS: Only one transaction exists for the key")

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    test_transaction_idempotency()
    print("TRANSACTION IDEMPOTENCY TEST PASSED")