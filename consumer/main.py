import asyncio
import random

import httpx
from faststream import AckPolicy, FastStream, Logger
from faststream.rabbit import RabbitBroker, RabbitMessage

from app.broker import PAYMENTS_DLQ, PAYMENTS_DLX, PAYMENTS_QUEUE, declare_topology
from app.config import get_settings
from app.db import SessionFactory
from app.models import PaymentStatus
from app.payment_service import PaymentService
from app.schemas import PaymentCreatedEvent

settings = get_settings()
broker = RabbitBroker(settings.rabbitmq_url, graceful_timeout=30)
app = FastStream(broker)


class PaymentProcessor:
    async def process(self) -> bool:
        await asyncio.sleep(random.uniform(2, 5))
        return random.random() < 0.9


processor = PaymentProcessor()


async def send_webhook(url: str, payment_id: str, status: PaymentStatus) -> bool:
    payload = {"payment_id": payment_id, "status": status.value}

    async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
        for attempt in range(3):
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"X-Payment-Id": payment_id},
                )
                response.raise_for_status()
                return True
            except httpx.HTTPError:
                if attempt < 2:
                    await asyncio.sleep(2**attempt)

    return False


@app.after_startup
async def setup_rabbit() -> None:
    await declare_topology(broker)


@broker.subscriber(PAYMENTS_QUEUE, ack_policy=AckPolicy.MANUAL)
async def consume_payment(
    body: dict,
    msg: RabbitMessage,
    logger: Logger,
) -> None:
    attempt = int(msg.headers.get("x-delivery-count", 0)) + 1

    try:
        event = PaymentCreatedEvent.model_validate(body)
        await _process_payment(event, logger)
    except Exception:
        if attempt < 3:
            await asyncio.sleep(2 ** (attempt - 1))
            await msg.raw_message.reject(requeue=True)
            return

        await msg.raw_message.reject(requeue=False)
        return

    await msg.ack()


async def _process_payment(event: PaymentCreatedEvent, logger: Logger) -> None:
    async with SessionFactory() as session:
        service = PaymentService(session)
        payment = await service.get(event.payment_id)

        if payment.status is PaymentStatus.PENDING:
            success = await processor.process()
            final_status = PaymentStatus.SUCCEEDED if success else PaymentStatus.FAILED
            await service.mark_processed(payment, final_status)
        else:
            final_status = payment.status

        if payment.webhook_delivered_at is not None:
            logger.info("Webhook already delivered for payment %s", payment.id)
            return

        webhook_url = payment.webhook_url
        payment_id = str(payment.id)

    delivered = await send_webhook(webhook_url, payment_id, final_status)

    if delivered:
        async with SessionFactory() as session:
            service = PaymentService(session)
            payment = await service.get(event.payment_id)
            await service.mark_webhook_delivered(payment)
        logger.info("Payment %s processed with status=%s", payment_id, final_status.value)
    else:
        logger.error("Webhook delivery failed after 3 attempts for payment %s", payment_id)


async def main() -> None:
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
