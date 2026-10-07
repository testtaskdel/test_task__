from app.models import Currency
from app.payment_service import build_request_hash
from app.schemas import PaymentCreate


def make_payload(amount: str = "100.00", order_id: int = 1) -> PaymentCreate:
    return PaymentCreate(
        amount=amount,
        currency=Currency.RUB,
        description="test",
        metadata={"order_id": order_id},
        webhook_url="https://example.com/hook",
    )


def test_same_payload_produces_same_hash():
    payload = make_payload()

    assert build_request_hash(payload) == build_request_hash(payload)


def test_different_payloads_produce_different_hashes():
    assert build_request_hash(make_payload()) != build_request_hash(make_payload(order_id=2))


def test_payment_response_uses_payment_id():
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.models import PaymentStatus
    from app.schemas import PaymentResponse

    payment_id = uuid4()
    response = PaymentResponse.model_validate(
        {
            "id": payment_id,
            "amount": "100.00",
            "currency": Currency.RUB,
            "description": "test",
            "payment_metadata": {"order_id": 1},
            "status": PaymentStatus.PENDING,
            "idempotency_key": "order-1",
            "webhook_url": "https://example.com/hook",
            "created_at": datetime.now(timezone.utc),
            "processed_at": None,
            "webhook_delivered_at": None,
        }
    )

    assert response.model_dump(mode="json")["payment_id"] == str(payment_id)
