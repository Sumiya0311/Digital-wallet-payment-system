from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_admin
from app.models.user import User
from app.jobs.withdrawal_job import process_pending_withdrawals

router = APIRouter(
    prefix="/withdrawals",
    tags=["Withdrawals"]
)


@router.post("/process-due")
def process_due_withdrawals(
    admin: User = Depends(get_current_admin)
):
    return process_pending_withdrawals()