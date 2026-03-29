"""phase4_rule_guardrails

Revision ID: 20260329_0007
Revises: 20260329_0006
Create Date: 2026-03-29

"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_0007"
down_revision = "20260329_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("automation_rules") as batch_op:
        batch_op.add_column(sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("max_runs_per_hour", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("last_run_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("automation_rules") as batch_op:
        batch_op.drop_column("last_run_at")
        batch_op.drop_column("max_runs_per_hour")
        batch_op.drop_column("cooldown_seconds")
