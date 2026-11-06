from pydantic import BaseModel, Field, ConfigDict


class MerchantCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=150)
    business_category: str = Field(min_length=2, max_length=100)
    user_id: int = Field(gt=0)


class MerchantResponse(BaseModel):
    id: int
    user_id: int
    business_name: str
    business_category: str
    merchant_code: str
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)