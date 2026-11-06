import logging

from app.database import SessionLocal
from app.services.cashback_service import process_due_cashbacks


logger = logging.getLogger(__name__)


def run_cashback_job():
    """Process eligible pending cashback automatically."""

    db = SessionLocal()

    try:
        result = process_due_cashbacks(
            db=db,
            batch_size=100
        )

        logger.info(
            "Cashback job completed: %s",
            result
        )

        print("CASHBACK JOB RESULT:", result)

    except Exception:
        logger.exception("Cashback job failed")

    finally:
        db.close()