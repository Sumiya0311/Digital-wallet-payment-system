import logging
from decimal import Decimal

from sqlalchemy import func, case
from app.database import SessionLocal
from app.models.wallet import Wallet
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")


def run_reconciliation():
    db = SessionLocal()

    try:
        mismatches = []

        # 1. Check every wallet against its ledger account.
        wallets = db.query(Wallet).all()

        for wallet in wallets:
            account = db.query(Account).filter(
                Account.wallet_id == wallet.id
            ).first()

            if not account:
                mismatches.append(
                    f"Wallet {wallet.id}: ledger account missing"
                )
                continue

            entries = db.query(LedgerEntry).filter(
                LedgerEntry.account_id == account.id
            ).all()

            calculated = ZERO

            for entry in entries:
                amount = Decimal(str(entry.amount))

                if entry.entry_type == "Credit":
                    calculated += amount
                else:
                    calculated -= amount

            wallet_balance = Decimal(str(wallet.balance))
            account_balance = Decimal(str(account.balance))

            if wallet_balance != account_balance:
                mismatches.append(
                    f"Wallet {wallet.id}: wallet={wallet_balance}, "
                    f"account={account_balance}"
                )

            if account_balance != calculated:
                mismatches.append(
                    f"Wallet {wallet.id}: account={account_balance}, "
                    f"ledger={calculated}"
                )

        # 2. Check total debits and credits globally.
        total_debits = db.query(
            func.coalesce(func.sum(LedgerEntry.amount), 0)
        ).filter(
            LedgerEntry.entry_type == "Debit"
        ).scalar()

        total_credits = db.query(
            func.coalesce(func.sum(LedgerEntry.amount), 0)
        ).filter(
            LedgerEntry.entry_type == "Credit"
        ).scalar()

        total_debits = Decimal(str(total_debits))
        total_credits = Decimal(str(total_credits))

        if total_debits != total_credits:
            mismatches.append(
                f"Ledger imbalance: debits={total_debits}, "
                f"credits={total_credits}"
            )

        result = {
            "wallets_checked": len(wallets),
            "total_debits": str(total_debits),
            "total_credits": str(total_credits),
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "status": "PASSED" if not mismatches else "FAILED"
        }

        if mismatches:
            logger.error("RECONCILIATION FAILED: %s", result)
        else:
            logger.info("RECONCILIATION PASSED: %s", result)

        return result

    except Exception:
        logger.exception("Reconciliation job encountered an error")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run_reconciliation())