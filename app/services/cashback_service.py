from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.cashback import Cashback
from app.models.transaction import Transaction
from app.models.account import Account
from app.models.wallet import Wallet

from app.services.ledger_service import record_ledger_entries


CENT = Decimal("0.01")
CASHBACK_RATE = Decimal("0.02")
MAX_CASHBACK = Decimal("50.00")


def create_pending_cashback(
    db: Session,
    transaction: Transaction
):
    """Create 2% pending cashback, capped at Rs.50."""

    if transaction.type != "Merchant Payment":
        return None

    if transaction.status != "Success":
        raise ValueError("Cashback requires a successful payment")

    existing = db.query(Cashback).filter(
        Cashback.transaction_id == transaction.id
    ).first()

    if existing:
        return existing

    payment_amount = Decimal(str(transaction.amount))

    cashback_amount = min(
        (payment_amount * CASHBACK_RATE).quantize(
            CENT,
            rounding=ROUND_HALF_UP
        ),
        MAX_CASHBACK
    )

    if cashback_amount <= 0:
        return None

    cashback = Cashback(
        transaction_id=transaction.id,
        user_id=transaction.initiated_by,
        amount=cashback_amount,
        status="Pending",
        eligible_at=datetime.utcnow() + timedelta(hours=24)
    )

    db.add(cashback)
    db.flush()

    return cashback


def cancel_pending_cashback(
    db: Session,
    transaction_id: int
):
    """Cancel pending cashback when its payment is refunded."""

    cashback = (
        db.query(Cashback)
        .filter(Cashback.transaction_id == transaction_id)
        .with_for_update()
        .first()
    )

    if cashback and cashback.status == "Pending":
        cashback.status = "Cancelled"
        cashback.updated_at = datetime.utcnow()

    return cashback


def process_due_cashbacks(
    db: Session,
    batch_size: int = 100
):
    """
    Credit eligible cashback into customer wallets.

    Debit Cashback Pool.
    Credit User Wallet.
    """

    try:
        now = datetime.utcnow()

        if batch_size < 1:
            raise ValueError("Batch size must be positive")

        # DEBUG: Check server UTC time.
        print("SERVER UTC TIME:", now)

        # DEBUG: Check eligible pending cashback count.
        due_count = (
            db.query(Cashback)
            .filter(
                Cashback.status == "Pending",
                Cashback.eligible_at <= now
            )
            .count()
        )

        print("DUE CASHBACK COUNT:", due_count)

        # DEBUG: Display all pending cashback records.
        pending_records = (
            db.query(Cashback)
            .filter(Cashback.status == "Pending")
            .all()
        )

        for record in pending_records:
            print(
                "PENDING CASHBACK:",
                {
                    "id": record.id,
                    "transaction_id": record.transaction_id,
                    "amount": str(record.amount),
                    "eligible_at": record.eligible_at,
                    "status": record.status
                }
            )

        # Get eligible cashback IDs.
        cashback_ids = [
            row.id
            for row in (
                db.query(Cashback.id)
                .filter(
                    Cashback.status == "Pending",
                    Cashback.eligible_at <= now
                )
                .order_by(Cashback.id)
                .limit(batch_size)
                .all()
            )
        ]

        processed = []

        for cashback_id in cashback_ids:

            candidate = (
                db.query(Cashback)
                .filter(Cashback.id == cashback_id)
                .first()
            )

            if not candidate:
                continue

            # Lock original payment first.
            original_payment = (
                db.query(Transaction)
                .filter(
                    Transaction.id == candidate.transaction_id
                )
                .with_for_update()
                .first()
            )

            cashback = (
                db.query(Cashback)
                .filter(Cashback.id == cashback_id)
                .with_for_update()
                .first()
            )

            if not cashback or cashback.status != "Pending":
                continue

            if cashback.eligible_at > now:
                continue

            if not original_payment:
                cashback.status = "Cancelled"
                cashback.updated_at = now
                continue

            if (
                original_payment.type != "Merchant Payment"
                or original_payment.status != "Success"
            ):
                cashback.status = "Cancelled"
                cashback.updated_at = now
                continue

            # Cancel cashback if a successful refund exists.
            successful_refund = (
                db.query(Transaction.id)
                .filter(
                    Transaction.original_transaction_id
                    == original_payment.id,
                    Transaction.type == "Merchant Refund",
                    Transaction.status == "Success"
                )
                .first()
            )

            if successful_refund:
                cashback.status = "Cancelled"
                cashback.updated_at = now
                continue

            # Find and lock customer wallet.
            customer_wallet = (
                db.query(Wallet)
                .filter(Wallet.owner_id == cashback.user_id)
                .with_for_update()
                .first()
            )

            if not customer_wallet:
                raise ValueError(
                    f"Wallet not found for cashback ID {cashback.id}"
                )

            if customer_wallet.status != "Active":
                raise ValueError(
                    f"Customer wallet is inactive for cashback ID {cashback.id}"
                )

            # Find Cashback Pool.
            cashback_pool = (
                db.query(Account)
                .filter(
                    Account.account_type == "Cashback Pool",
                    Account.wallet_id.is_(None)
                )
                .first()
            )

            if not cashback_pool:
                raise ValueError("Cashback Pool account not found")

            # Find customer ledger account.
            user_account = (
                db.query(Account)
                .filter(
                    Account.wallet_id == customer_wallet.id,
                    Account.account_type == "User Wallet"
                )
                .first()
            )

            if not user_account:
                raise ValueError("Customer ledger account not found")

            # Create cashback transaction.
            cashback_transaction = Transaction(
                transaction_ref=(
                    f"CB-{cashback.id}-{now.strftime('%Y%m%d%H%M%S')}"
                ),
                type="Cashback",
                amount=Decimal(str(cashback.amount)).quantize(CENT),
                status="Pending",
                initiated_by=cashback.user_id,
                original_transaction_id=original_payment.id,
                idempotency_key=f"CASHBACK-{cashback.id}",
                description="Merchant payment cashback"
            )

            db.add(cashback_transaction)
            db.flush()

            # Double-entry ledger posting.
            record_ledger_entries(
                db=db,
                transaction=cashback_transaction,
                debit_account=cashback_pool,
                credit_account=user_account,
                amount=Decimal(str(cashback.amount)).quantize(CENT)
            )

            cashback.status = "Credited"
            cashback.credited_at = datetime.utcnow()
            cashback.updated_at = datetime.utcnow()

            processed.append(cashback.id)

        db.commit()

        return {
            "message": "Cashback processing completed",
            "processed_count": len(processed),
            "cashback_ids": processed
        }

    except Exception:
        db.rollback()
        raise