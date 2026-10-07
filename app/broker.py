import asyncio
from datetime import datetime, timezone

from faststream.rabbit import ExchangeType, QueueType, RabbitBroker, RabbitExchange, RabbitQueue
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionFactory
from app.models import OutboxEvent

settings = get_settings()

PAYMENTS_QUEUE = RabbitQueue(
    "payments.new",
    durable=True,
    queue_type=QueueType.QUORUM,
    declare=True,
    arguments={
        "x-delivery-limit": 10,
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": "payments.dlq",
    },
)
PAYMENTS_DLQ = RabbitQueue("payments.dlq", durable=True, declare=True)
PAYMENTS_DLX = RabbitExchange(
    "payments.dlx",
    type=ExchangeType.DIRECT,
    durable=True,
)

broker = RabbitBroker(settings.rabbitmq_url, graceful_timeout=30)


async def declare_topology(rabbit_broker: RabbitBroker) -> None:
    """Declare the queues and exchange required by the payment flow."""
    await rabbit_broker.declare_exchange(PAYMENTS_DLX)
    await rabbit_broker.declare_queue(PAYMENTS_QUEUE)
    dlq = await rabbit_broker.declare_queue(PAYMENTS_DLQ)
    await dlq.bind(PAYMENTS_DLX.name, routing_key=PAYMENTS_DLQ.name)


class OutboxPublisher:
    def __init__(self, stop_event: asyncio.Event):
        self.stop_event = stop_event

    async def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                published = await self.publish_batch()
                if not published:
                    await asyncio.wait_for(
                        self.stop_event.wait(),
                        timeout=settings.outbox_poll_interval,
                    )
            except TimeoutError:
                pass
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(settings.outbox_poll_interval)

    async def publish_batch(self) -> bool:
        async with SessionFactory() as session:
            async with session.begin():
                result = await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.sent_at.is_(None))
                    .order_by(OutboxEvent.created_at)
                    .limit(settings.outbox_batch_size)
                    .with_for_update(skip_locked=True)
                )
                events = result.scalars().all()
                if not events:
                    return False

                for event in events:
                    await broker.publish(
                        event.payload,
                        queue=PAYMENTS_QUEUE,
                        persist=True,
                        message_id=str(event.id),
                        message_type=event.event_type,
                        headers={"event_id": str(event.id)},
                    )
                    event.sent_at = datetime.now(timezone.utc)

                return True
