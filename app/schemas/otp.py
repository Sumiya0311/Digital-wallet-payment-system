from typing import Literal

from pydantic import BaseModel, Field


class OTPGenerateRequest(BaseModel):
    purpose: Literal[
        "wallet_transaction",
        "bank_account"
    ] = "wallet_transaction"


class OTPVerifyRequest(BaseModel):
    otp: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$"
    )


class OTPResponse(BaseModel):
    message: str
    expires_in: int