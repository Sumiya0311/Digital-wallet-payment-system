import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.jobs.withdrawal_job import process_pending_withdrawals
from app.jobs.cashback_job import run_cashback_job
from app.jobs.reconciliation_job import run_reconciliation


logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler():
    if scheduler.running:
        return

    # 1. Process pending withdrawals every 5 minutes
    scheduler.add_job(
        func=process_pending_withdrawals,
        trigger="interval",
        minutes=5,
        id="process_pending_withdrawals",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60
    )

    # 2. Process eligible cashback every hour
    scheduler.add_job(
        func=run_cashback_job,
        trigger="interval",
        hours=1,
        id="process_due_cashbacks",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300
    )

    # 3. Reconcile the ledger daily at 00:00 UTC
    scheduler.add_job(
        func=run_reconciliation,
        trigger="cron",
        hour=0,
        minute=0,
        id="daily_ledger_reconciliation",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600
    )

    scheduler.start()

    logger.info(
        "Scheduler started: withdrawals every 5 minutes, "
        "cashback every hour, reconciliation daily at 00:00 UTC"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")