from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)


class BankAccountCreate(BaseModel):
    account_holder_name: str = Field(
        min_length=2,
        max_length=100
    )

    bank_name: str = Field(
        min_length=2,
        max_length=100
    )

    account_number: str = Field(
        min_length=9,
        max_length=18,
        pattern=r"^[0-9]{9,18}$"
    )

    ifsc_code: str = Field(
        min_length=11,
        max_length=11
    )

    otp: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$"
    )

    @field_validator("ifsc_code")
    @classmethod
    def validate_ifsc(cls, value: str) -> str:
        value = value.strip().upper()

        import re

        if not re.fullmatch(
            r"[A-Z]{4}0[A-Z0-9]{6}",
            value
        ):
            raise ValueError("Invalid IFSC code")

        return value


class BankAccountResponse(BaseModel):
    id: int
    account_holder_name: str
    bank_name: str
    masked_account_number: str
    ifsc_code: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )