from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WalletResponse(BaseModel):
    id: int
    owner_id: int
    wallet_number: str
    balance: Decimal
    kyc_level: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class WalletPinCreate(BaseModel):
    pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^[0-9]{4}$"
    )
class WalletPinVerify(BaseModel):
    pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^[0-9]{4}$"
    )

class WalletPinChange(BaseModel):
    current_pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^[0-9]{4}$"
    )

    new_pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^[0-9]{4}$"
    )