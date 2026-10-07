import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

from app.models import Currency, PaymentStatus


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Currency
    description: str = Field(min_length=1, max_length=2000)
    metadata: dict = Field(default_factory=dict)
    webhook_url: AnyHttpUrl

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict) -> dict:
        if len(value) > 50:
            raise ValueError("metadata contains too many fields")
        return value


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: uuid.UUID = Field(validation_alias="id", serialization_alias="payment_id")
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict = Field(
        validation_alias="payment_metadata",
        serialization_alias="metadata",
    )
    status: PaymentStatus
    idempotency_key: str
    webhook_url: AnyHttpUrl
    created_at: datetime
    processed_at: datetime | None = None
    webhook_delivered_at: datetime | None = None


class PaymentCreatedEvent(BaseModel):
    payment_id: uuid.UUID
