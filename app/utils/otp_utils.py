import secrets
from datetime import datetime, timedelta, timezone

from app.auth.utils import hash_password, verify_password


def generate_otp():
    """Generate a secure six-digit OTP."""
    return f"{secrets.randbelow(1000000):06d}"


def hash_otp(otp: str):
    """Hash OTP before database storage."""
    return hash_password(otp)


def verify_otp(plain_otp: str, hashed_otp: str):
    """Verify OTP against its stored hash."""
    return verify_password(plain_otp, hashed_otp)


def get_otp_expiry():
    """Set OTP expiry to five minutes in UTC."""
    return datetime.utcnow() + timedelta(minutes=5)