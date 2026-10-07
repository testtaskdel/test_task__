from pathlib import Path

from app.broker import PAYMENTS_DLQ, PAYMENTS_DLX, PAYMENTS_QUEUE
from faststream.rabbit import QueueType

ROOT = Path(__file__).resolve().parents[1]


def test_payments_queue_uses_quorum_queue_type():
    assert PAYMENTS_QUEUE.arguments["x-queue-type"] == QueueType.QUORUM.value


def test_payments_queue_is_declared_and_dead_letters_to_dlq():
    assert PAYMENTS_QUEUE.declare is True
    assert PAYMENTS_QUEUE.arguments["x-dead-letter-exchange"] == PAYMENTS_DLX.name
    assert PAYMENTS_QUEUE.arguments["x-dead-letter-routing-key"] == PAYMENTS_DLQ.name


def test_dlq_is_declared():
    assert PAYMENTS_DLQ.declare is True


def test_postgres_is_not_published_to_host_port():
    compose = (ROOT / "docker-compose.yml").read_text()
    postgres_block = compose.split("  rabbitmq:", 1)[0]
    assert '"5432:5432"' not in postgres_block


def test_consumer_waits_for_api_topology():
    compose = (ROOT / "docker-compose.yml").read_text()
    consumer_block = compose.split("  consumer:", 1)[1]
    assert "api:" in consumer_block
    assert "condition: service_healthy" in consumer_block


def test_consumer_has_manual_entrypoint():
    consumer = (ROOT / "consumer" / "main.py").read_text()
    assert "asyncio.run(main())" in consumer


def test_migrations_are_resilient_to_existing_enum_types():
    migration = (ROOT / "migrations/versions/0001_initial.py").read_text()
    assert "duplicate_object" in migration
    assert "create_type=False" in migration


def test_webhook_migration_is_idempotent():
    migration = (ROOT / "migrations/versions/0002_webhook_delivery.py").read_text()
    assert '"webhook_delivered_at" not in columns' in migration
