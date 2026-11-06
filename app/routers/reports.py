from datetime import date, datetime, timedelta
from decimal import Decimal
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.wallet import Wallet
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry
from app.models.merchant import Merchant


router = APIRouter(prefix="/reports", tags=["Reports"])

ZERO = Decimal("0.00")


def amount(value):
    return Decimal(str(value or ZERO)).quantize(Decimal("0.01"))


def require_role(user, role):
    if user.role != role:
        raise HTTPException(
            status_code=403,
            detail=f"Only {role} can access this report"
        )


def get_wallet_account(db, user):
    wallet = db.query(Wallet).filter(
        Wallet.owner_id == user.id
    ).first()

    if not wallet:
        raise HTTPException(404, "Wallet not found")

    account = db.query(Account).filter(
        Account.wallet_id == wallet.id
    ).first()

    if not account:
        raise HTTPException(404, "Wallet account not found")

    return wallet, account


def date_bounds(from_date, to_date):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            422, "from_date cannot be after to_date"
        )

    start = (
        datetime.combine(from_date, datetime.min.time())
        if from_date else None
    )
    end = (
        datetime.combine(
            to_date + timedelta(days=1),
            datetime.min.time()
        )
        if to_date else None
    )
    return start, end


@router.get("/admin-dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, "Admin")

    today = datetime.utcnow().date()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)

    wallets = db.query(Wallet).all()
    transactions = db.query(Transaction).all()

    today_by_type = defaultdict(
        lambda: {"count": 0, "volume": ZERO}
    )

    failed = 0
    on_hold = 0
    cashback_paid = ZERO

    for txn in transactions:
        if txn.status == "Failed":
            failed += 1

        if txn.status == "On Hold":
            on_hold += 1

        if txn.type == "Cashback" and txn.status == "Success":
            cashback_paid += amount(txn.amount)

        if start <= txn.created_at < end:
            group = today_by_type[txn.type]
            group["count"] += 1

            if txn.status == "Success":
                group["volume"] += amount(txn.amount)

    return {
        "total_wallet_balance": str(
            sum((amount(w.balance) for w in wallets), ZERO)
        ),
        "wallet_count": len(wallets),
        "today_transaction_count": sum(
            x["count"] for x in today_by_type.values()
        ),
        "today_transactions_by_type": {
            key: {
                "count": value["count"],
                "successful_volume": str(value["volume"])
            }
            for key, value in today_by_type.items()
        },
        "failed_transactions": failed,
        "transactions_on_hold": on_hold,
        "cashback_paid": str(cashback_paid)
    }


@router.get("/ledger-summary")
def ledger_summary(
    from_date: date = Query(None),
    to_date: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, "Admin")

    start, end = date_bounds(from_date, to_date)

    query = db.query(LedgerEntry)

    if start:
        query = query.filter(LedgerEntry.created_at >= start)

    if end:
        query = query.filter(LedgerEntry.created_at < end)

    entries = query.all()
    accounts = db.query(Account).filter(
        Account.wallet_id.is_(None)
    ).all()

    debits = sum(
        (amount(e.amount) for e in entries
         if e.entry_type == "Debit"),
        ZERO
    )
    credits = sum(
        (amount(e.amount) for e in entries
         if e.entry_type == "Credit"),
        ZERO
    )

    return {
        "system_accounts": [
            {
                "account_id": account.id,
                "account_type": account.account_type,
                "balance": str(amount(account.balance))
            }
            for account in accounts
        ],
        "period_total_debits": str(debits),
        "period_total_credits": str(credits),
        "balanced": debits == credits,
        "entries_checked": len(entries)
    }


@router.get("/merchant-sales")
def merchant_sales(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, "Merchant")

    merchant = db.query(Merchant).filter(
        Merchant.user_id == current_user.id
    ).first()

    if not merchant:
        raise HTTPException(404, "Merchant profile not found")

    wallet, account = get_wallet_account(db, current_user)

    rows = (
        db.query(LedgerEntry, Transaction)
        .join(
            Transaction,
            LedgerEntry.transaction_id == Transaction.id
        )
        .filter(LedgerEntry.account_id == account.id)
        .all()
    )

    daily = defaultdict(
        lambda: {
            "payments": 0,
            "sales": ZERO,
            "refunds": ZERO,
            "net_received": ZERO
        }
    )

    total_sales = ZERO
    total_refunds = ZERO
    payment_count = 0
    refund_count = 0

    for entry, txn in rows:
        day = entry.created_at.date().isoformat()
        value = amount(entry.amount)

        if (
            txn.type == "Merchant Payment"
            and entry.entry_type == "Credit"
        ):
            daily[day]["payments"] += 1
            daily[day]["sales"] += value
            daily[day]["net_received"] += value
            total_sales += value
            payment_count += 1

        elif (
            txn.type == "Merchant Refund"
            and entry.entry_type == "Debit"
        ):
            daily[day]["refunds"] += value
            daily[day]["net_received"] -= value
            total_refunds += value
            refund_count += 1

    return {
        "merchant": merchant.business_name,
        "merchant_code": merchant.merchant_code,
        "payment_count": payment_count,
        "refund_count": refund_count,
        "recorded_sales": str(total_sales),
        "recorded_refunds": str(total_refunds),
        "net_received_after_refunds": str(
            total_sales - total_refunds
        ),
        "platform_fees_paid": "0.00",
        "platform_fee_note": (
            "Current payment implementation does not "
            "record the required 1% merchant fee."
        ),
        "daily_sales": [
            {
                "date": day,
                "payment_count": values["payments"],
                "sales": str(values["sales"]),
                "refunds": str(values["refunds"]),
                "net_received": str(values["net_received"])
            }
            for day, values in sorted(daily.items())
        ]
    }


@router.get("/my-spending")
def my_spending(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, "User")

    wallet, account = get_wallet_account(db, current_user)

    rows = (
        db.query(LedgerEntry, Transaction)
        .join(
            Transaction,
            LedgerEntry.transaction_id == Transaction.id
        )
        .filter(LedgerEntry.account_id == account.id)
        .all()
    )

    monthly = defaultdict(
        lambda: {
            "p2p_transfers": ZERO,
            "merchant_payments": ZERO,
            "withdrawals": ZERO,
            "cashback_earned": ZERO
        }
    )

    for entry, txn in rows:
        month = entry.created_at.strftime("%Y-%m")
        value = amount(entry.amount)

        if entry.entry_type == "Debit":
            if txn.type == "P2P Transfer":
                monthly[month]["p2p_transfers"] += value

            elif txn.type == "Merchant Payment":
                monthly[month]["merchant_payments"] += value

            elif txn.type == "Withdrawal":
                monthly[month]["withdrawals"] += value

        elif (
            entry.entry_type == "Credit"
            and txn.type == "Cashback"
        ):
            monthly[month]["cashback_earned"] += value

    return {
        "wallet_number": wallet.wallet_number,
        "monthly_spending": [
            {
                "month": month,
                **{
                    key: str(value)
                    for key, value in values.items()
                }
            }
            for month, values in sorted(monthly.items())
        ],
        "note": (
            "Merchant payments are grouped by transaction "
            "type. Business-category breakdown requires "
            "reliable merchant attribution."
        )
    }