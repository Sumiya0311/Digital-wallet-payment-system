from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.database import SessionLocal
from app.models.transaction import Transaction
from app.models.fraud_flag import FraudFlag
from app.services.fraud_detection_service import detect_fraud


def test_rapid_transaction_fraud():
    db = SessionLocal()

    try:
        # Use existing test user ID 5.
        user_id = 5
        now = datetime.utcnow()

        # Insert five qualifying transactions.
        # They will be rolled back after the test.
        for i in range(5):
            transaction = Transaction(
                transaction_ref=f"TEST-{uuid4().hex[:16].upper()}",
                type="P2P Transfer",
                amount=Decimal("1.00"),
                status="Success",
                initiated_by=user_id,
                description=f"Temporary fraud test {i + 1}",
                created_at=now - timedelta(seconds=i + 1)
            )
            db.add(transaction)

        db.flush()

        # Create sixth pending transaction.
        sixth_transaction = Transaction(
            transaction_ref=f"TEST-{uuid4().hex[:16].upper()}",
            type="P2P Transfer",
            amount=Decimal("1.00"),
            status="Pending",
            initiated_by=user_id,
            description="Sixth rapid transaction test"
        )

        db.add(sixth_transaction)
        db.flush()

        fraud_flag = detect_fraud(
            db=db,
            transaction=sixth_transaction
        )

        db.flush()

        print("Transaction ID:", sixth_transaction.id)
        print("Transaction status:", sixth_transaction.status)
        print("Is flagged:", sixth_transaction.is_flagged)
        print("Fraud flag created:", fraud_flag is not None)

        if fraud_flag is not None:
            print("Fraud reason:", fraud_flag.reason)
            print("Fraud flag status:", fraud_flag.status)

        assert sixth_transaction.status == "On Hold"
        assert sixth_transaction.is_flagged is True
        assert fraud_flag is not None
        assert fraud_flag.status == "Pending"

        print("PASS: Rapid transaction fraud detection")

    finally:
        # Never commit these test transactions.
        db.rollback()
        db.close()
        print("Test records rolled back.")


if __name__ == "__main__":
    test_rapid_transaction_fraud()