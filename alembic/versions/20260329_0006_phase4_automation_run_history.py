"""phase4_automation_run_history

Revision ID: 20260329_0006
Revises: 20260329_0005
Create Date: 2026-03-29

"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_0006"
down_revision = "20260329_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_rule_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("automation_rule_id", sa.String(length=36), sa.ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("actions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_source", sa.String(length=30), nullable=False),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_automation_rule_runs_automation_rule_id", "automation_rule_runs", ["automation_rule_id"], unique=False)
    op.create_index("ix_automation_rule_runs_organization_id", "automation_rule_runs", ["organization_id"], unique=False)
    op.create_index("ix_automation_rule_runs_status", "automation_rule_runs", ["status"], unique=False)
    op.create_index("ix_automation_rule_runs_run_source", "automation_rule_runs", ["run_source"], unique=False)
    op.create_index("ix_automation_rule_runs_executed_at", "automation_rule_runs", ["executed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_automation_rule_runs_executed_at", table_name="automation_rule_runs")
    op.drop_index("ix_automation_rule_runs_run_source", table_name="automation_rule_runs")
    op.drop_index("ix_automation_rule_runs_status", table_name="automation_rule_runs")
    op.drop_index("ix_automation_rule_runs_organization_id", table_name="automation_rule_runs")
    op.drop_index("ix_automation_rule_runs_automation_rule_id", table_name="automation_rule_runs")
    op.drop_table("automation_rule_runs")
