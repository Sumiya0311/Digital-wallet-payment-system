from fastapi import APIRouter, BackgroundTasks, Depends

from app.models.user import User
from app.auth.dependencies import get_current_user
from app.utils.email_utils import send_notification_email


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)


@router.post("/send-test")
def send_test_notification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    background_tasks.add_task(
        send_notification_email,
        receiver_email=current_user.email,
        subject="Digital Wallet - Test Notification",
        message_text=(
            "Your Digital Wallet email notification "
            "service is working successfully."
        )
    )

    return {
        "message": "Notification queued for background delivery",
        "recipient": current_user.email
    }