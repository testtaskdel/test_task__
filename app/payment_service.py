import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import IdempotencyConflictError, PaymentNotFoundError
from app.models import OutboxEvent, Payment, PaymentStatus
from app.schemas import PaymentCreate


def build_request_hash(payload: PaymentCreate) -> str:
    normalized = {
        "amount": format(payload.amount, "f"),
        "currency": payload.currency.value,
        "description": payload.description,
        "metadata": payload.metadata,
        "webhook_url": str(payload.webhook_url),
    }
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payload: PaymentCreate, idempotency_key: str) -> Payment:
        request_hash = build_request_hash(payload)
        existing = await self._get_by_idempotency_key(idempotency_key)
        if existing is not None:
            self._ensure_same_request(existing, request_hash)
            return existing

        payment = Payment(
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            payment_metadata=payload.metadata,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            webhook_url=str(payload.webhook_url),
            status=PaymentStatus.PENDING,
        )
        self.session.add(payment)
        await self.session.flush()

        self.session.add(
            OutboxEvent(
                aggregate_id=payment.id,
                event_type="payments.new",
                payload={"payment_id": str(payment.id)},
            )
        )
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get(self, payment_id) -> Payment:
        payment = await self.session.get(Payment, payment_id)
        if payment is None:
            raise PaymentNotFoundError
        return payment

    async def mark_processed(self, payment: Payment, status: PaymentStatus) -> bool:
        if payment.status is not PaymentStatus.PENDING:
            return False

        payment.status = status
        payment.processed_at = datetime.now(timezone.utc)
        await self.session.commit()
        return True

    async def mark_webhook_delivered(self, payment: Payment) -> None:
        if payment.webhook_delivered_at is None:
            payment.webhook_delivered_at = datetime.now(timezone.utc)
            await self.session.commit()

    async def _get_by_idempotency_key(self, key: str) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _ensure_same_request(payment: Payment, request_hash: str) -> None:
        if payment.request_hash != request_hash:
            raise IdempotencyConflictError(
                "Idempotency-Key was already used with another request"
            )


async def create_payment_safely(
    session: AsyncSession,
    payload: PaymentCreate,
    idempotency_key: str,
) -> Payment:
    service = PaymentService(session)
    try:
        return await service.create(payload, idempotency_key)
    except IntegrityError:
        await session.rollback()
        existing = await service._get_by_idempotency_key(idempotency_key)
        if existing is None:
            raise
        service._ensure_same_request(existing, build_request_hash(payload))
        return existing
