"""phase3_webhook_idempotency

Revision ID: 20260329_0004
Revises: 20260329_0003
Create Date: 2026-03-29

"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_0004"
down_revision = "20260329_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_webhook_events_source", "webhook_events", ["source"], unique=False)
    op.create_index("ix_webhook_events_event_hash", "webhook_events", ["event_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_webhook_events_event_hash", table_name="webhook_events")
    op.drop_index("ix_webhook_events_source", table_name="webhook_events")
    op.drop_table("webhook_events")
