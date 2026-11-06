from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)


class KYCSubmitRequest(BaseModel):
    pan_number: str = Field(
        min_length=10,
        max_length=10
    )

    aadhaar_last4: str = Field(
        pattern=r"^[0-9]{4}$"
    )

    full_name: str = Field(
        min_length=2,
        max_length=100
    )

    date_of_birth: date

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, value: str) -> str:
        import re

        value = value.strip().upper()

        if not re.fullmatch(
            r"[A-Z]{5}[0-9]{4}[A-Z]",
            value
        ):
            raise ValueError("Invalid PAN number format")

        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        if value >= date.today():
            raise ValueError(
                "Date of birth must be in the past"
            )

        return value


class KYCRejectRequest(BaseModel):
    rejection_reason: str = Field(
        min_length=5,
        max_length=255
    )


class KYCResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    date_of_birth: date
    status: str
    rejection_reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )