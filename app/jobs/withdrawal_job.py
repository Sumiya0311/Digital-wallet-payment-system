import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.account import Account
from app.models.bank_account import BankAccount
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.models.withdrawal import Withdrawal
from app.services.ledger_service import record_ledger_entries


MIN_PENDING_TIME = timedelta(minutes=10)


def process_pending_withdrawals():
    """Process withdrawals that have been pending for at least 10 minutes."""

    db: Session = SessionLocal()

    processed = 0
    completed = 0
    failed = 0

    try:
        cutoff = datetime.utcnow() - MIN_PENDING_TIME

        pending_ids = [
            row[0]
            for row in (
                db.query(Withdrawal.id)
                .filter(
                    Withdrawal.status == "Pending",
                    Withdrawal.created_at <= cutoff
                )
                .order_by(Withdrawal.created_at.asc())
                .all()
            )
        ]

        for withdrawal_id in pending_ids:
            try:
                # Lock withdrawal to prevent duplicate processing.
                withdrawal = (
                    db.query(Withdrawal)
                    .filter(Withdrawal.id == withdrawal_id)
                    .with_for_update()
                    .first()
                )

                if not withdrawal or withdrawal.status != "Pending":
                    db.rollback()
                    continue

                if withdrawal.created_at > datetime.utcnow() - MIN_PENDING_TIME:
                    db.rollback()
                    continue

                original = (
                    db.query(Transaction)
                    .filter(
                        Transaction.id == withdrawal.transaction_id
                    )
                    .first()
                )

                if not original or original.status != "Pending":
                    raise ValueError(
                        "Original pending transaction not found"
                    )

                bank_account = (
                    db.query(BankAccount)
                    .filter(
                        BankAccount.id == withdrawal.bank_account_id
                    )
                    .first()
                )

                if not bank_account:
                    raise ValueError("Destination bank account not found")

                clearing_account = (
                    db.query(Account)
                    .filter(
                        Account.account_type == "Withdrawal Clearing"
                    )
                    .first()
                )

                if not clearing_account:
                    raise ValueError(
                        "Withdrawal Clearing account not found"
                    )

                amount = Decimal(str(withdrawal.amount))

                if bank_account.account_number.endswith("0000"):
                    # Failed withdrawal: return funds to the wallet.
                    wallet = (
                        db.query(Wallet)
                        .filter(Wallet.owner_id == withdrawal.user_id)
                        .first()
                    )

                    if not wallet:
                        raise ValueError("User wallet not found")

                    wallet_account = (
                        db.query(Account)
                        .filter(
                            Account.wallet_id == wallet.id,
                            Account.account_type.in_(
                                ("User Wallet", "Merchant Wallet")
                            )
                        )
                        .first()
                    )

                    if not wallet_account:
                        raise ValueError(
                            "Wallet ledger account not found"
                        )

                    reversal = Transaction(
                        transaction_ref=(
                            f"WRV-{secrets.token_hex(8).upper()}"
                        ),
                        type="Withdrawal Reversal",
                        amount=amount,
                        status="Pending",
                        initiated_by=withdrawal.user_id,
                        original_transaction_id=original.id,
                        idempotency_key=(
                            f"withdrawal-failure-{withdrawal.id}"
                        ),
                        description="Bank withdrawal failed; funds returned"
                    )

                    db.add(reversal)
                    db.flush()

                    # Debit Clearing; Credit User Wallet.
                    record_ledger_entries(
                        db=db,
                        transaction=reversal,
                        debit_account=clearing_account,
                        credit_account=wallet_account,
                        amount=amount
                    )

                    original.status = "Failed"
                    withdrawal.status = "Failed"
                    withdrawal.failure_reason = (
                        "Bank account rejected withdrawal "
                        "(account number ends in 0000)"
                    )

                    outcome = "Failed"

                else:
                    # Successful withdrawal: settle to bank.
                    settlement_account = (
                        db.query(Account)
                        .filter(
                            Account.account_type == "Bank Settlement"
                        )
                        .first()
                    )

                    if not settlement_account:
                        raise ValueError(
                            "Bank Settlement account not found"
                        )

                    settlement = Transaction(
                        transaction_ref=(
                            f"WST-{secrets.token_hex(8).upper()}"
                        ),
                        type="Withdrawal",
                        amount=amount,
                        status="Pending",
                        initiated_by=withdrawal.user_id,
                        original_transaction_id=original.id,
                        idempotency_key=(
                            f"withdrawal-settlement-{withdrawal.id}"
                        ),
                        description="Bank withdrawal settlement"
                    )

                    db.add(settlement)
                    db.flush()

                    # Debit Clearing; Credit Bank Settlement.
                    record_ledger_entries(
                        db=db,
                        transaction=settlement,
                        debit_account=clearing_account,
                        credit_account=settlement_account,
                        amount=amount
                    )

                    original.status = "Success"
                    withdrawal.status = "Completed"
                    withdrawal.failure_reason = None

                    outcome = "Completed"

                withdrawal.processed_at = datetime.utcnow()

                db.commit()

                processed += 1

                if outcome == "Completed":
                    completed += 1
                else:
                    failed += 1

            except Exception as exc:
                db.rollback()
                print(
                    f"Withdrawal {withdrawal_id} processing error: {exc}"
                )

        return {
            "processed": processed,
            "completed": completed,
            "failed": failed
        }

    finally:
        db.close()