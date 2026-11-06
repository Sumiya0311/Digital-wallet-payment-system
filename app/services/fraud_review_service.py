from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.fraud_flag import FraudFlag
from app.models.ledger_entry import LedgerEntry

from app.services.ledger_service import record_ledger_entries
from app.services.transaction_limit_service import (
    validate_outgoing_limits
)


def review_fraud_transaction(
    db: Session,
    admin: User,
    transaction_id: int,
    decision: str,
    notes: str = ""
):
    """
    Admin review of fraud-flagged transactions.

    Approved:
        Execute a held P2P transfer after revalidation.

    Rejected:
        Mark the held transaction as Failed without
        transferring money.

    The review decision and ledger posting are
    committed atomically.
    """

    try:
        # 1. Verify Admin authorization
        if admin.role != "Admin":
            raise ValueError(
                "Only administrators can review fraud"
            )

        # 2. Validate review decision
        if decision not in ("Approved", "Rejected"):
            raise ValueError(
                "Decision must be Approved or Rejected"
            )

        # 3. Lock the transaction
        transaction = (
            db.query(Transaction)
            .filter(
                Transaction.id == transaction_id
            )
            .populate_existing()
            .with_for_update()
            .first()
        )

        if not transaction:
            raise ValueError("Transaction not found")

        # 4. Lock fraud flag
        flag = (
            db.query(FraudFlag)
            .filter(
                FraudFlag.transaction_id == transaction_id
            )
            .with_for_update()
            .first()
        )

        if not flag:
            raise ValueError("Fraud flag not found")

        # 5. Prevent repeated reviews
        if (
            transaction.status != "On Hold"
            or not transaction.is_flagged
            or flag.status != "Pending"
        ):
            raise ValueError(
                "Transaction is not eligible for review"
            )

        # 6. Ensure held funds have not been posted
        existing_entries = (
            db.query(LedgerEntry)
            .filter(
                LedgerEntry.transaction_id == transaction.id
            )
            .count()
        )

        if existing_entries:
            raise ValueError(
                "Held transaction already has ledger entries"
            )

        # 7. Reject transaction
        if decision == "Rejected":
            transaction.status = "Failed"

            flag.status = "Rejected"
            flag.reviewed_by = admin.id
            flag.review_notes = notes
            flag.reviewed_at = datetime.utcnow()

            db.commit()
            db.refresh(transaction)

            return transaction

        # 8. Approval currently supports P2P only
        if transaction.type != "P2P Transfer":
            raise ValueError(
                "Approval is currently supported "
                "only for P2P transfers"
            )

        # 9. Verify original receiver
        if transaction.receiver_wallet_id is None:
            raise ValueError(
                "Original receiver wallet is missing. "
                "Cannot safely approve this transaction"
            )

        # 10. Lock sender wallet
        sender_wallet = (
            db.query(Wallet)
            .filter(
                Wallet.owner_id == transaction.initiated_by
            )
            .populate_existing()
            .with_for_update()
            .first()
        )

        if not sender_wallet:
            raise ValueError("Sender wallet not found")

        # 11. Lock receiver wallet
        receiver_wallet = (
            db.query(Wallet)
            .filter(
                Wallet.id == transaction.receiver_wallet_id
            )
            .populate_existing()
            .with_for_update()
            .first()
        )

        if not receiver_wallet:
            raise ValueError("Receiver wallet not found")

        if sender_wallet.id == receiver_wallet.id:
            raise ValueError(
                "Cannot approve a transfer to the same wallet"
            )

        # 12. Check wallet status
        if (
            sender_wallet.status != "Active"
            or receiver_wallet.status != "Active"
        ):
            raise ValueError(
                "Both wallets must be active"
            )

        # 13. Verify user accounts
        sender_user = (
            db.query(User)
            .filter(
                User.id == transaction.initiated_by
            )
            .first()
        )

        receiver_user = (
            db.query(User)
            .filter(
                User.id == receiver_wallet.owner_id
            )
            .first()
        )

        if (
            not sender_user
            or not sender_user.is_active
            or not receiver_user
            or not receiver_user.is_active
        ):
            raise ValueError(
                "Sender or receiver account is inactive"
            )

        # 14. Verify available balance
        amount = Decimal(str(transaction.amount))

        if Decimal(str(sender_wallet.balance)) < amount:
            raise ValueError(
                "Insufficient sender wallet balance"
            )

        # 15. Revalidate KYC daily/monthly limits
        # Exclude this held transaction to avoid
        # counting its amount twice.
        validate_outgoing_limits(
            db=db,
            wallet=sender_wallet,
            amount=amount,
            exclude_transaction_id=transaction.id
        )

        # 16. Find sender ledger account
        sender_account = (
            db.query(Account)
            .filter(
                Account.wallet_id == sender_wallet.id,
                Account.account_type == "User Wallet"
            )
            .first()
        )

        # 17. Find receiver ledger account
        receiver_account = (
            db.query(Account)
            .filter(
                Account.wallet_id == receiver_wallet.id,
                Account.account_type == "User Wallet"
            )
            .first()
        )

        if not sender_account or not receiver_account:
            raise ValueError(
                "Sender or receiver ledger account not found"
            )

        # 18. Post approved transfer
        record_ledger_entries(
            db=db,
            transaction=transaction,
            debit_account=sender_account,
            credit_account=receiver_account,
            amount=amount,
            fraud_approval=True
        )

        # 19. Record Admin approval
        flag.status = "Approved"
        flag.reviewed_by = admin.id
        flag.review_notes = notes
        flag.reviewed_at = datetime.utcnow()

        # 20. Commit both operations together
        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise