from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.models.wallet import Wallet


CENT = Decimal("0.01")

KYC_LIMITS = {
    "Minimum": {
        "daily": Decimal("10000.00"),
        "monthly": Decimal("25000.00"),
    },
    "Full": {
        "daily": Decimal("25000.00"),
        "monthly": Decimal("100000.00"),
    },
}

OUTGOING_TYPES = (
    "P2P Transfer",
    "Merchant Payment",
    "Withdrawal",
)


def validate_outgoing_limits(
    db: Session,
    wallet: Wallet,
    amount: Decimal,
    exclude_transaction_id: int | None = None
):
    """
    Validate combined outgoing daily/monthly limits.

    Counts successful, pending, and held outgoing
    transactions. Excludes the transaction currently
    being approved to avoid double-counting.

    Caller must lock the sender wallet before calling
    this function to serialize outgoing operations.
    """

    try:
        amount = Decimal(str(amount))

        if (
            not amount.is_finite()
            or amount <= 0
            or amount != amount.quantize(CENT)
        ):
            raise ValueError("Invalid transaction amount")

    except (InvalidOperation, TypeError) as exc:
        raise ValueError(
            "Invalid transaction amount"
        ) from exc

    limits = KYC_LIMITS.get(wallet.kyc_level)

    if limits is None:
        raise ValueError("Unsupported wallet KYC level")

    now = datetime.utcnow()

    day_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    month_start = day_start.replace(day=1)

    def outgoing_total(start_date):
        query = db.query(
            func.coalesce(
                func.sum(Transaction.amount),
                0
            )
        ).filter(
            Transaction.initiated_by == wallet.owner_id,
            Transaction.type.in_(OUTGOING_TYPES),
            Transaction.status.in_(
                ("Success", "Pending", "On Hold")
            ),
            Transaction.original_transaction_id.is_(None),
            Transaction.created_at >= start_date
        )

        if exclude_transaction_id is not None:
            query = query.filter(
                Transaction.id != exclude_transaction_id
            )

        result = query.scalar()

        return Decimal(str(result))

    daily_total = outgoing_total(day_start)
    monthly_total = outgoing_total(month_start)

    if daily_total + amount > limits["daily"]:
        raise ValueError(
            f"Daily outgoing limit of "
            f"Rs.{limits['daily']} exceeded"
        )

    if monthly_total + amount > limits["monthly"]:
        raise ValueError(
            f"Monthly outgoing limit of "
            f"Rs.{limits['monthly']} exceeded"
        )

    return True