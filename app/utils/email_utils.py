import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


def send_otp_email(receiver_email: str, otp: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_host, smtp_email, smtp_password]):
        raise ValueError("SMTP configuration is incomplete")

    message = EmailMessage()
    message["Subject"] = "Digital Wallet - OTP Verification"
    message["From"] = smtp_email
    message["To"] = receiver_email

    message.set_content(
        f"""Hello,

Your Digital Wallet verification OTP is: {otp}

This OTP is valid for 5 minutes.

Do not share this OTP with anyone.

If you did not request this OTP, please ignore this email.

Regards,
Digital Wallet Team
"""
    )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(message)

def send_notification_email(
    receiver_email: str,
    subject: str,
    message_text: str
):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_host, smtp_email, smtp_password]):
        raise ValueError("SMTP configuration is incomplete")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_email
    message["To"] = receiver_email

    message.set_content(
        f"""Hello,

{message_text}

Regards,
Digital Wallet Team
"""
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(message)