from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


# --------------------------------------------------
# 1. P2P Transfer Request
# --------------------------------------------------

class P2PTransferRequest(BaseModel):
    receiver_wallet_number: str = Field(
        min_length=5,
        max_length=20
    )

    amount: Decimal = Field(
        gt=Decimal("0.00"),
        max_digits=12,
        decimal_places=2
    )

    pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^[0-9]{4}$"
    )

    otp: str | None = Field(
        default=None,
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$"
    )

    idempotency_key: str = Field(
        min_length=10,
        max_length=100
    )

    description: str | None = Field(
        default=None,
        max_length=255
    )


# --------------------------------------------------
# 2. Add Money Request
# --------------------------------------------------

class AddMoneyRequest(BaseModel):
    amount: Decimal = Field(
        gt=Decimal("0.00"),
        max_digits=12,
        decimal_places=2
    )

    idempotency_key: str = Field(
        min_length=10,
        max_length=100
    )

    description: str | None = Field(
        default="Wallet top-up",
        max_length=255
    )


# --------------------------------------------------
# 3. Merchant Payment Request
# --------------------------------------------------

class MerchantPaymentRequest(BaseModel):
    merchant_code: str = Field(
        min_length=5,
        max_length=30
    )

    amount: Decimal = Field(
        gt=Decimal("0.00"),
        max_digits=12,
        decimal_places=2
    )

    pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^[0-9]{4}$"
    )

    otp: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$"
    )

    idempotency_key: str = Field(
        min_length=10,
        max_length=100
    )

    description: str | None = Field(
        default="Merchant payment",
        max_length=255
    )


# --------------------------------------------------
# 4. Transaction Response
# --------------------------------------------------

class TransactionResponse(BaseModel):
    id: int
    transaction_ref: str
    type: str
    amount: Decimal
    status: str
    description: str | None = None

    model_config = ConfigDict(
        from_attributes=True
    )


# --------------------------------------------------
# 5. Merchant Refund Request
# --------------------------------------------------

class MerchantRefundRequest(BaseModel):
    original_transaction_id: int = Field(
        gt=0
    )

    amount: Decimal = Field(
        gt=Decimal("0.00"),
        max_digits=12,
        decimal_places=2
    )

    idempotency_key: str = Field(
        min_length=10,
        max_length=100
    )

    description: str | None = Field(
        default="Merchant refund",
        max_length=255
    )


# --------------------------------------------------
# 6. Withdrawal Request
# --------------------------------------------------

class WithdrawalRequest(BaseModel):
    bank_account_id: int = Field(
        gt=0
    )

    amount: Decimal = Field(
        ge=Decimal("100.00"),
        max_digits=12,
        decimal_places=2
    )

    pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^[0-9]{4}$"
    )

    idempotency_key: str = Field(
        min_length=10,
        max_length=100
    )

    description: str | None = Field(
        default="Wallet withdrawal",
        max_length=255
    )


# --------------------------------------------------
# 7. Withdrawal Reversal Request
# --------------------------------------------------

class WithdrawalReversalRequest(BaseModel):
    original_transaction_id: int = Field(
        gt=0
    )

    idempotency_key: str = Field(
        min_length=10,
        max_length=100
    )

    description: str | None = Field(
        default="Withdrawal reversal",
        max_length=255
    )