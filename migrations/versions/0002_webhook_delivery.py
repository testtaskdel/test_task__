"""track webhook delivery

Revision ID: 0002_webhook_delivery
Revises: 0001_initial
Create Date: 2026-10-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_webhook_delivery"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("payments")}
    if "webhook_delivered_at" not in columns:
        op.add_column(
            "payments",
            sa.Column("webhook_delivered_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("payments")}
    if "webhook_delivered_at" in columns:
        op.drop_column("payments", "webhook_delivered_at")
