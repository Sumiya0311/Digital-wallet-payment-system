from decimal import Decimal, InvalidOperation
import secrets

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.account import Account
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry

from app.services.ledger_service import record_ledger_entries
from app.services.cashback_service import cancel_pending_cashback


CENT = Decimal("0.01")


def process_merchant_refund(
    db: Session,
    merchant_user: User,
    original_transaction_id: int,
    amount: Decimal,
    idempotency_key: str,
    description: str = "Merchant refund"
):
    try:
        # 1. Validate refund amount
        try:
            amount = Decimal(str(amount))

            if not amount.is_finite() or amount <= 0:
                raise ValueError("Refund amount must be positive")

            if amount != amount.quantize(CENT):
                raise ValueError(
                    "Refund amount cannot have more than two decimal places"
                )

            amount = amount.quantize(CENT)

        except (InvalidOperation, TypeError):
            raise ValueError("Invalid refund amount")

        # 2. Validate idempotency key
        if not idempotency_key or not idempotency_key.strip():
            raise ValueError("Idempotency key is required")

        # 3. Check merchant identity
        if merchant_user.role != "Merchant":
            raise ValueError("Only merchants can process refunds")

        merchant = db.query(Merchant).filter(
            Merchant.user_id == merchant_user.id
        ).first()

        if not merchant or not merchant.is_verified:
            raise ValueError("Verified merchant account required")

        # 4. Check idempotency
        existing = db.query(Transaction).filter(
            Transaction.initiated_by == merchant_user.id,
            Transaction.idempotency_key == idempotency_key
        ).first()

        if existing:
            if (
                existing.type == "Merchant Refund"
                and existing.original_transaction_id == original_transaction_id
                and Decimal(str(existing.amount)).quantize(CENT) == amount
            ):
                return existing

            raise ValueError("Idempotency key already used")

        # 5. Lock original payment
        original = (
            db.query(Transaction)
            .filter(Transaction.id == original_transaction_id)
            .with_for_update()
            .first()
        )

        if not original:
            raise ValueError("Original transaction not found")

        if original.type != "Merchant Payment":
            raise ValueError("Original transaction is not a merchant payment")

        if original.status != "Success":
            raise ValueError("Only successful payments can be refunded")

        # 6. Verify original customer
        customer = db.query(User).filter(
            User.id == original.initiated_by
        ).first()

        if not customer or not customer.is_active:
            raise ValueError("Original customer account is unavailable")

        # 7. Lock merchant and customer wallets
        merchant_wallet = (
            db.query(Wallet)
            .filter(Wallet.owner_id == merchant_user.id)
            .with_for_update()
            .first()
        )

        customer_wallet = (
            db.query(Wallet)
            .filter(Wallet.owner_id == customer.id)
            .with_for_update()
            .first()
        )

        if not merchant_wallet or not customer_wallet:
            raise ValueError("Merchant or customer wallet not found")

        if merchant_wallet.status != "Active":
            raise ValueError("Merchant wallet is not active")

        if customer_wallet.status != "Active":
            raise ValueError("Customer wallet is not active")

        # 8. Find ledger accounts
        merchant_account = db.query(Account).filter(
            Account.wallet_id == merchant_wallet.id,
            Account.account_type == "Merchant Wallet"
        ).with_for_update().first()

        customer_account = db.query(Account).filter(
            Account.wallet_id == customer_wallet.id,
            Account.account_type == "User Wallet"
        ).with_for_update().first()

        if not merchant_account or not customer_account:
            raise ValueError("Required ledger accounts not found")

        # 9. Verify merchant received original payment
        original_credit = db.query(LedgerEntry).filter(
            LedgerEntry.transaction_id == original.id,
            LedgerEntry.account_id == merchant_account.id,
            LedgerEntry.entry_type == "Credit"
        ).first()

        if not original_credit:
            raise ValueError(
                "This merchant did not receive the original payment"
            )

        # 10. Calculate previous successful refunds
        previous_refunds = db.query(Transaction).filter(
            Transaction.original_transaction_id == original.id,
            Transaction.type == "Merchant Refund",
            Transaction.status == "Success"
        ).all()

        refunded_amount = sum(
            (
                Decimal(str(refund.amount))
                for refund in previous_refunds
            ),
            Decimal("0.00")
        )

        original_amount = Decimal(str(original.amount)).quantize(CENT)

        remaining_amount = original_amount - refunded_amount

        if amount > remaining_amount:
            raise ValueError(
                f"Refund exceeds remaining refundable amount: "
                f"{remaining_amount}"
            )

        if amount > Decimal(str(merchant_wallet.balance)):
            raise ValueError("Insufficient merchant wallet balance")

        # 11. Create refund transaction
        refund = Transaction(
            transaction_ref=f"REF-{secrets.token_hex(8).upper()}",
            type="Merchant Refund",
            amount=amount,
            status="Pending",
            initiated_by=merchant_user.id,
            original_transaction_id=original.id,
            idempotency_key=idempotency_key,
            description=description
        )

        db.add(refund)
        db.flush()

        # 12. Process double-entry ledger refund
        record_ledger_entries(
            db=db,
            transaction=refund,
            debit_account=merchant_account,
            credit_account=customer_account,
            amount=amount
        )

        # 13. Cancel pending cashback for original payment
        cancel_pending_cashback(
            db=db,
            transaction_id=original.id
        )

        # 14. Commit refund and cashback cancellation together
        db.commit()
        db.refresh(refund)

        return refund

    except Exception:
        db.rollback()
        raise