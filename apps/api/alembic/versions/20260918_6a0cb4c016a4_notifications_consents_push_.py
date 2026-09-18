"""notifications consents push subscriptions

Revision ID: 6a0cb4c016a4
Revises: 8372ab940a8e
Create Date: 2026-09-18 02:21:41.981197

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6a0cb4c016a4"
down_revision: str | None = "8372ab940a8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consents",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("user_id", "kind", "granted_at"),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.String(length=1024), nullable=False),
        sa.Column("p256dh", sa.String(length=256), nullable=False),
        sa.Column("auth", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index(
        op.f("ix_push_subscriptions_user_id"), "push_subscriptions", ["user_id"], unique=False
    )
    op.create_table(
        "scheduled_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("channel", sa.String(length=8), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ref_type", sa.String(length=32), nullable=True),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=80), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("last_error", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        "ix_scheduled_notifications_pending_due",
        "scheduled_notifications",
        ["due_at"],
        unique=False,
        postgresql_where=sa.text("sent_at IS NULL AND cancelled_at IS NULL"),
    )
    op.create_index(
        "ix_scheduled_notifications_ref",
        "scheduled_notifications",
        ["ref_type", "ref_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_notifications_user_id"),
        "scheduled_notifications",
        ["user_id"],
        unique=False,
    )
    op.add_column("users", sa.Column("reminder_local_time", sa.Time(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "reminder_local_time")
    op.drop_index(op.f("ix_scheduled_notifications_user_id"), table_name="scheduled_notifications")
    op.drop_index("ix_scheduled_notifications_ref", table_name="scheduled_notifications")
    op.drop_index(
        "ix_scheduled_notifications_pending_due",
        table_name="scheduled_notifications",
        postgresql_where=sa.text("sent_at IS NULL AND cancelled_at IS NULL"),
    )
    op.drop_table("scheduled_notifications")
    op.drop_index(op.f("ix_push_subscriptions_user_id"), table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_table("consents")
