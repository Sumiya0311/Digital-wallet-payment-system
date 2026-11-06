from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.wallet import Wallet
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction


CENT = Decimal("0.01")


# Debit-normal accounts
DEBIT_NORMAL_ACCOUNTS = {
    "Bank Settlement",
    "Cashback Pool",
}


# Credit-normal accounts
CREDIT_NORMAL_ACCOUNTS = {
    "User Wallet",
    "Merchant Wallet",
    "Fees",
    "Hold",
    "Opening Equity",
    "Withdrawal Clearing",
}


def record_ledger_entries(
    db: Session,
    transaction: Transaction,
    debit_account: Account,
    credit_account: Account,
    amount: Decimal,
    final_status: str = "Success",
    fraud_approval: bool = False
):
    """
    Record a balanced double-entry ledger transaction.

    Normal transactions must be Pending.

    Fraud-held P2P transactions may be posted only
    when fraud_approval=True, after the Admin review
    service has completed authorization and validation.

    The caller is responsible for committing.
    """

    # 1. Validate transaction and account IDs
    if transaction.id is None:
        raise ValueError("Transaction must be saved first")

    if debit_account.id is None or credit_account.id is None:
        raise ValueError("Both accounts must be saved first")

    debit_id = debit_account.id
    credit_id = credit_account.id

    if debit_id == credit_id:
        raise ValueError(
            "Debit and credit accounts must be different"
        )

    # 2. Validate amount
    try:
        amount = Decimal(str(amount))

        if not amount.is_finite() or amount <= 0:
            raise ValueError("Amount must be positive")

        if amount != amount.quantize(CENT):
            raise ValueError(
                "Amount cannot have more than two decimal places"
            )

        amount = amount.quantize(CENT)

    except (InvalidOperation, TypeError):
        raise ValueError("Invalid transaction amount")

    # 3. Validate final status
    if final_status not in {"Success", "Pending"}:
        raise ValueError(
            "Final status must be Success or Pending"
        )

    if (
        final_status == "Pending"
        and transaction.type != "Withdrawal"
    ):
        raise ValueError(
            "Only withdrawal reservations can remain Pending"
        )

    if fraud_approval and final_status != "Success":
        raise ValueError(
            "Fraud approval must finalize as Success"
        )

    # 4. Lock transaction
    locked_transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction.id)
        .populate_existing()
        .with_for_update()
        .first()
    )

    if not locked_transaction:
        raise ValueError("Transaction not found")

    # Normal ledger posting requires Pending status.
    # A held P2P transfer requires explicit fraud approval.
    if fraud_approval:
        if not (
            locked_transaction.type == "P2P Transfer"
            and locked_transaction.status == "On Hold"
            and locked_transaction.is_flagged
            and locked_transaction.receiver_wallet_id is not None
        ):
            raise ValueError(
                "Transaction is not eligible for fraud approval"
            )
    elif locked_transaction.status != "Pending":
        raise ValueError(
            "Only pending transactions can be posted"
        )

    if (
        final_status == "Pending"
        and locked_transaction.type != "Withdrawal"
    ):
        raise ValueError(
            "Only withdrawal reservations can remain Pending"
        )

    transaction_amount = Decimal(
        str(locked_transaction.amount)
    ).quantize(CENT)

    if transaction_amount != amount:
        raise ValueError(
            "Ledger amount must match transaction amount"
        )

    # 5. Lock accounts in consistent order
    account_ids = sorted([debit_id, credit_id])

    locked_accounts = (
        db.query(Account)
        .filter(Account.id.in_(account_ids))
        .order_by(Account.id)
        .populate_existing()
        .with_for_update()
        .all()
    )

    accounts = {
        account.id: account
        for account in locked_accounts
    }

    debit_account = accounts.get(debit_id)
    credit_account = accounts.get(credit_id)

    if not debit_account or not credit_account:
        raise ValueError(
            "Debit or credit account not found"
        )

    # 6. Validate account types
    supported_account_types = (
        DEBIT_NORMAL_ACCOUNTS
        | CREDIT_NORMAL_ACCOUNTS
    )

    for account in (debit_account, credit_account):

        if account.account_type not in supported_account_types:
            raise ValueError(
                f"Unsupported account type: {account.account_type}"
            )

        is_wallet_account = account.account_type in {
            "User Wallet",
            "Merchant Wallet"
        }

        if is_wallet_account and account.wallet_id is None:
            raise ValueError(
                "Wallet account must be linked to a wallet"
            )

        if not is_wallet_account and account.wallet_id is not None:
            raise ValueError(
                "System account cannot be linked to a wallet"
            )

    # 7. Lock associated wallets
    wallet_ids = sorted({
        account.wallet_id
        for account in (debit_account, credit_account)
        if account.wallet_id is not None
    })

    wallets_by_id = {}

    if wallet_ids:
        locked_wallets = (
            db.query(Wallet)
            .filter(Wallet.id.in_(wallet_ids))
            .order_by(Wallet.id)
            .populate_existing()
            .with_for_update()
            .all()
        )

        wallets_by_id = {
            wallet.id: wallet
            for wallet in locked_wallets
        }

    # 8. Validate wallet balances and status
    for account in (debit_account, credit_account):

        if account.wallet_id is None:
            continue

        wallet = wallets_by_id.get(account.wallet_id)

        if not wallet:
            raise ValueError("Wallet not found")

        if wallet.status != "Active":
            raise ValueError("Wallet is not active")

        wallet_balance = Decimal(
            str(wallet.balance)
        ).quantize(CENT)

        account_balance = Decimal(
            str(account.balance)
        ).quantize(CENT)

        if wallet_balance != account_balance:
            raise ValueError(
                "Wallet and account balances are inconsistent"
            )

    # 9. Validate original P2P participants
    if fraud_approval:
        sender_wallet = wallets_by_id.get(
            debit_account.wallet_id
        )
        receiver_wallet = wallets_by_id.get(
            credit_account.wallet_id
        )

        if (
            debit_account.account_type != "User Wallet"
            or credit_account.account_type != "User Wallet"
            or sender_wallet is None
            or receiver_wallet is None
            or sender_wallet.owner_id
            != locked_transaction.initiated_by
            or receiver_wallet.id
            != locked_transaction.receiver_wallet_id
            or sender_wallet.id == receiver_wallet.id
        ):
            raise ValueError(
                "Fraud approval wallet details do not match"
            )

    # 10. Prevent duplicate ledger posting
    existing_entries = (
        db.query(LedgerEntry)
        .filter(
            LedgerEntry.transaction_id
            == locked_transaction.id
        )
        .count()
    )

    if existing_entries:
        raise ValueError(
            "Ledger entries already exist for this transaction"
        )

    # 11. Read balances
    debit_balance = Decimal(
        str(debit_account.balance)
    ).quantize(CENT)

    credit_balance = Decimal(
        str(credit_account.balance)
    ).quantize(CENT)

    # 12. Calculate debit account balance
    if debit_account.account_type in DEBIT_NORMAL_ACCOUNTS:
        new_debit_balance = debit_balance + amount
    else:
        new_debit_balance = debit_balance - amount

    # 13. Calculate credit account balance
    if credit_account.account_type in CREDIT_NORMAL_ACCOUNTS:
        new_credit_balance = credit_balance + amount
    else:
        new_credit_balance = credit_balance - amount

    # 14. Prevent negative balances
    if new_debit_balance < 0 or new_credit_balance < 0:
        raise ValueError(
            "Insufficient account balance"
        )

    # 15. Update ledger account balances
    debit_account.balance = new_debit_balance
    credit_account.balance = new_credit_balance

    # 16. Synchronize wallet balances
    for account in (debit_account, credit_account):
        if account.wallet_id is not None:
            wallets_by_id[
                account.wallet_id
            ].balance = account.balance

    # 17. Create debit ledger entry
    debit_entry = LedgerEntry(
        transaction_id=locked_transaction.id,
        account_id=debit_account.id,
        entry_type="Debit",
        amount=amount,
        balance_after=new_debit_balance
    )

    # 18. Create credit ledger entry
    credit_entry = LedgerEntry(
        transaction_id=locked_transaction.id,
        account_id=credit_account.id,
        entry_type="Credit",
        amount=amount,
        balance_after=new_credit_balance
    )

    db.add_all([
        debit_entry,
        credit_entry
    ])

    # 19. Update transaction status
    locked_transaction.status = final_status

    return debit_entry, credit_entry