from decimal import Decimal

from app.database import SessionLocal
from app.models.account import Account


SYSTEM_ACCOUNT_TYPES = [
    "Bank Settlement",
    "Cashback Pool",
    "Fees",
    "Withdrawal Clearing",
    "Hold",
    "Opening Equity",
]


def seed_system_accounts():
    db = SessionLocal()

    try:
        for account_type in SYSTEM_ACCOUNT_TYPES:
            existing_account = db.query(Account).filter(
                Account.account_type == account_type,
                Account.wallet_id.is_(None)
            ).first()

            if existing_account:
                print(f"Already exists: {account_type}")
                continue

            account = Account(
                account_type=account_type,
                wallet_id=None,
                balance=Decimal("0.00")
            )

            db.add(account)
            print(f"Created: {account_type}")

        db.commit()
        print("System accounts setup completed.")

    except Exception as exc:
        db.rollback()
        print("Error:", str(exc))
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_system_accounts()