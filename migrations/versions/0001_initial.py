"""create payments and outbox

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect, text

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _ensure_enum(bind, name: str, values: tuple[str, ...]) -> None:
    literals = ", ".join(f"'{value}'" for value in values)
    bind.execute(
        text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({literals}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    _ensure_enum(bind, "payment_status", ("pending", "succeeded", "failed"))
    _ensure_enum(bind, "currency", ("RUB", "USD", "EUR"))

    if not inspector.has_table("payments"):
        payment_status = postgresql.ENUM(
            "pending", "succeeded", "failed",
            name="payment_status",
            create_type=False,
        )
        currency = postgresql.ENUM(
            "RUB", "USD", "EUR",
            name="currency",
            create_type=False,
        )
        op.create_table(
            "payments",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("currency", currency, nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("status", payment_status, nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("request_hash", sa.String(length=64), nullable=False),
            sa.Column("webhook_url", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key"),
        )

    inspector = inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("payments")} if inspector.has_table("payments") else set()
    if "ix_payments_status" not in indexes:
        op.create_index("ix_payments_status", "payments", ["status"])
    if "ix_payments_created_at" not in indexes:
        op.create_index("ix_payments_created_at", "payments", ["created_at"])

    if not inspector.has_table("outbox"):
        op.create_table(
            "outbox",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["aggregate_id"], ["payments.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = inspect(bind)
    outbox_indexes = {index["name"] for index in inspector.get_indexes("outbox")} if inspector.has_table("outbox") else set()
    if "ix_outbox_unsent" not in outbox_indexes:
        op.create_index(
            "ix_outbox_unsent",
            "outbox",
            ["created_at"],
            postgresql_where=sa.text("sent_at IS NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("outbox"):
        op.drop_index("ix_outbox_unsent", table_name="outbox")
        op.drop_table("outbox")
    if inspector.has_table("payments"):
        op.drop_index("ix_payments_created_at", table_name="payments")
        op.drop_index("ix_payments_status", table_name="payments")
        op.drop_table("payments")
    bind.execute(text("DROP TYPE IF EXISTS currency"))
    bind.execute(text("DROP TYPE IF EXISTS payment_status"))
