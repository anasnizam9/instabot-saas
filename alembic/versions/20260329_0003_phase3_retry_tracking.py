"""phase3_retry_tracking

Revision ID: 20260329_0003
Revises: 20260329_0002
Create Date: 2026-03-29

"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_0003"
down_revision = "20260329_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scheduled_posts") as batch_op:
        batch_op.add_column(sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("last_attempt_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scheduled_posts") as batch_op:
        batch_op.drop_column("last_attempt_at")
        batch_op.drop_column("attempt_count")
