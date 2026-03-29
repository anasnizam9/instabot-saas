"""phase4_automation_analytics

Revision ID: 20260329_0005
Revises: 20260329_0004
Create Date: 2026-03-29

"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_0005"
down_revision = "20260329_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("automation_rules"):
        op.create_table(
            "automation_rules",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("rule_type", sa.String(length=50), nullable=False),
            sa.Column("rule_config", sa.Text(), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    existing_automation_indexes = {idx["name"] for idx in inspector.get_indexes("automation_rules")}
    if "ix_automation_rules_organization_id" not in existing_automation_indexes:
        op.create_index("ix_automation_rules_organization_id", "automation_rules", ["organization_id"], unique=False)
    if "ix_automation_rules_rule_type" not in existing_automation_indexes:
        op.create_index("ix_automation_rules_rule_type", "automation_rules", ["rule_type"], unique=False)
    if "ix_automation_rules_is_enabled" not in existing_automation_indexes:
        op.create_index("ix_automation_rules_is_enabled", "automation_rules", ["is_enabled"], unique=False)

    if not inspector.has_table("analytics_snapshots"):
        op.create_table(
            "analytics_snapshots",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("metric_name", sa.String(length=80), nullable=False),
            sa.Column("metric_value", sa.Float(), nullable=False),
            sa.Column("snapshot_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    existing_analytics_indexes = {idx["name"] for idx in inspector.get_indexes("analytics_snapshots")}
    if "ix_analytics_snapshots_organization_id" not in existing_analytics_indexes:
        op.create_index("ix_analytics_snapshots_organization_id", "analytics_snapshots", ["organization_id"], unique=False)
    if "ix_analytics_snapshots_metric_name" not in existing_analytics_indexes:
        op.create_index("ix_analytics_snapshots_metric_name", "analytics_snapshots", ["metric_name"], unique=False)
    if "ix_analytics_snapshots_snapshot_at" not in existing_analytics_indexes:
        op.create_index("ix_analytics_snapshots_snapshot_at", "analytics_snapshots", ["snapshot_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_analytics_snapshots_snapshot_at", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_metric_name", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_organization_id", table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")

    op.drop_index("ix_automation_rules_is_enabled", table_name="automation_rules")
    op.drop_index("ix_automation_rules_rule_type", table_name="automation_rules")
    op.drop_index("ix_automation_rules_organization_id", table_name="automation_rules")
    op.drop_table("automation_rules")
