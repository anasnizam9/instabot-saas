"""phase2_instagram_integration

Revision ID: 20260329_0002
Revises: 20260329_0001
Create Date: 2026-03-29

"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_0002"
down_revision = "20260329_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instagram_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ig_user_id", sa.String(length=100), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_instagram_accounts_organization_id", "instagram_accounts", ["organization_id"], unique=False)
    op.create_index("ix_instagram_accounts_ig_user_id", "instagram_accounts", ["ig_user_id"], unique=True)

    op.create_table(
        "scheduled_posts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("instagram_account_id", sa.String(length=36), sa.ForeignKey("instagram_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("media_urls", sa.Text(), nullable=False),
        sa.Column("publish_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, default="draft"),
        sa.Column("instagram_post_id", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_scheduled_posts_instagram_account_id", "scheduled_posts", ["instagram_account_id"], unique=False)
    op.create_index("ix_scheduled_posts_status", "scheduled_posts", ["status"], unique=False)
    op.create_index("ix_scheduled_posts_instagram_post_id", "scheduled_posts", ["instagram_post_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_scheduled_posts_instagram_post_id", table_name="scheduled_posts")
    op.drop_index("ix_scheduled_posts_status", table_name="scheduled_posts")
    op.drop_index("ix_scheduled_posts_instagram_account_id", table_name="scheduled_posts")
    op.drop_table("scheduled_posts")

    op.drop_index("ix_instagram_accounts_ig_user_id", table_name="instagram_accounts")
    op.drop_index("ix_instagram_accounts_organization_id", table_name="instagram_accounts")
    op.drop_table("instagram_accounts")
