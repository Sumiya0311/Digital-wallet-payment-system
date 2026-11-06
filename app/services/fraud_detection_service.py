from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.models.fraud_flag import FraudFlag


# Configurable demonstration thresholds.
# These are NOT substitutes for the wallet's actual
# KYC and transaction-limit validations.
HIGH_AMOUNT_THRESHOLD = Decimal("10000.00")
RAPID_TRANSACTION_COUNT = 5
RAPID_TRANSACTION_WINDOW_MINUTES = 10

MONITORED_TYPES = (
    "P2P Transfer",
    "Merchant Payment",
    "Withdrawal",
)


def detect_fraud(
    db: Session,
    transaction: Transaction
):
    """
    Evaluate a transaction for basic fraud indicators.

    Call this before executing ledger movements.
    The caller is responsible for committing.
    """

    if transaction.type not in MONITORED_TYPES:
        return None

    # Avoid duplicate fraud flags.
    existing_flag = (
        db.query(FraudFlag)
        .filter(
            FraudFlag.transaction_id == transaction.id
        )
        .first()
    )

    if existing_flag:
        return existing_flag

    reasons = []

    amount = Decimal(str(transaction.amount))

    # Rule 1: High-value transaction
    if amount >= HIGH_AMOUNT_THRESHOLD:
        reasons.append(
            "High-value transaction detected"
        )

    # Rule 2: Too many recent transactions
    window_start = (
        datetime.utcnow()
        - timedelta(
            minutes=RAPID_TRANSACTION_WINDOW_MINUTES
        )
    )

    recent_count = (
        db.query(Transaction)
        .filter(
            Transaction.initiated_by
            == transaction.initiated_by,
            Transaction.id != transaction.id,
            Transaction.type.in_(MONITORED_TYPES),
            Transaction.original_transaction_id.is_(None),
            Transaction.created_at >= window_start,
            Transaction.status.in_(
                ["Pending", "Success", "On Hold"]
            )
        )
        .count()
    )

    if recent_count >= RAPID_TRANSACTION_COUNT:
        reasons.append(
            "Unusually frequent transactions detected"
        )

    if not reasons:
        return None

    fraud_flag = FraudFlag(
        transaction_id=transaction.id,
        user_id=transaction.initiated_by,
        reason="; ".join(reasons),
        status="Pending"
    )

    transaction.is_flagged = True
    transaction.status = "On Hold"

    db.add(fraud_flag)
    db.flush()

    return fraud_flag