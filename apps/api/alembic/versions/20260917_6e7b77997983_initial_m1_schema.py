"""initial m1 schema

Revision ID: 6e7b77997983
Revises:
Create Date: 2026-09-17 17:10:12.325422

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6e7b77997983"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_events_actor_occurred_at", "events", ["actor_id", "occurred_at"], unique=False
    )
    op.create_index("ix_events_occurred_at", "events", ["occurred_at"], unique=False)
    op.create_index("ix_events_subject", "events", ["subject_type", "subject_id"], unique=False)
    op.create_index(
        "ix_events_type_occurred_at", "events", ["event_type", "occurred_at"], unique=False
    )
    op.create_table(
        "reward_config",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rate_per_minute", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("daily_cap", sa.Integer(), nullable=False),
        sa.Column("streak_multipliers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reward_config_effective_from"), "reward_config", ["effective_from"], unique=False
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("google_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_sub"),
    )
    op.create_table(
        "village_levels",
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("xp_required", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.SmallInteger(), nullable=False),
        sa.Column("height", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("level"),
    )
    op.create_table(
        "villages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_type", sa.String(length=8), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("width", sa.SmallInteger(), nullable=False),
        sa.Column("height", sa.SmallInteger(), nullable=False),
        sa.Column("xp", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_type", "owner_id", name="uq_villages_owner"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "coin_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("ref_type", sa.String(length=32), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "ref_id", name="uq_coin_ledger_kind_ref"),
    )
    op.create_index(op.f("ix_coin_ledger_user_id"), "coin_ledger", ["user_id"], unique=False)
    op.create_table(
        "focus_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("target_seconds", sa.Integer(), nullable=True),
        sa.Column("intent", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("pause_reason", sa.String(length=16), nullable=True),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("focused_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_focus_sessions_one_active_per_user",
        "focus_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('running', 'paused')"),
    )
    op.create_index(
        "ix_focus_sessions_status_updated_at",
        "focus_sessions",
        ["status", "updated_at"],
        unique=False,
    )
    op.create_index(op.f("ix_focus_sessions_user_id"), "focus_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_focus_sessions_user_local_date",
        "focus_sessions",
        ["user_id", "local_date"],
        unique=False,
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_tags_owner_name"),
    )
    op.create_table(
        "retrospectives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mood", sa.SmallInteger(), nullable=False),
        sa.Column("intent_match", sa.String(length=8), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["focus_sessions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(op.f("ix_retrospectives_user_id"), "retrospectives", ["user_id"], unique=False)
    op.create_table(
        "session_segments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["focus_sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_session_segments_one_open_per_session",
        "session_segments",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "ix_session_segments_open_last_seen",
        "session_segments",
        ["last_seen_at"],
        unique=False,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        op.f("ix_session_segments_session_id"), "session_segments", ["session_id"], unique=False
    )
    op.create_table(
        "retro_tags",
        sa.Column("retro_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["retro_id"],
            ["retrospectives.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
        ),
        sa.PrimaryKeyConstraint("retro_id", "tag_id"),
    )

    # Seed data: reward constants live in the DB (CLAUDE.md rule 3), never in code.
    op.execute(
        sa.text(
            """
            INSERT INTO reward_config
                (id, effective_from, rate_per_minute, daily_cap, streak_multipliers, created_at)
            VALUES
                (gen_random_uuid(), '2026-01-01T00:00:00Z', 1.000, 300,
                 '{"3": 1.1, "7": 1.25, "30": 1.5}'::jsonb, now())
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO village_levels (level, xp_required, width, height) VALUES
                (1, 0, 16, 16),
                (2, 600, 16, 16),
                (3, 1800, 20, 20),
                (4, 4200, 20, 20),
                (5, 9000, 24, 24)
            """
        )
    )


def downgrade() -> None:
    op.drop_table("retro_tags")
    op.drop_index(op.f("ix_session_segments_session_id"), table_name="session_segments")
    op.drop_index(
        "ix_session_segments_open_last_seen",
        table_name="session_segments",
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.drop_index(
        "ix_session_segments_one_open_per_session",
        table_name="session_segments",
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.drop_table("session_segments")
    op.drop_index(op.f("ix_retrospectives_user_id"), table_name="retrospectives")
    op.drop_table("retrospectives")
    op.drop_table("tags")
    op.drop_index("ix_focus_sessions_user_local_date", table_name="focus_sessions")
    op.drop_index(op.f("ix_focus_sessions_user_id"), table_name="focus_sessions")
    op.drop_index("ix_focus_sessions_status_updated_at", table_name="focus_sessions")
    op.drop_index(
        "ix_focus_sessions_one_active_per_user",
        table_name="focus_sessions",
        postgresql_where=sa.text("status IN ('running', 'paused')"),
    )
    op.drop_table("focus_sessions")
    op.drop_index(op.f("ix_coin_ledger_user_id"), table_name="coin_ledger")
    op.drop_table("coin_ledger")
    op.drop_table("villages")
    op.drop_table("village_levels")
    op.drop_table("users")
    op.drop_index(op.f("ix_reward_config_effective_from"), table_name="reward_config")
    op.drop_table("reward_config")
    op.drop_index("ix_events_type_occurred_at", table_name="events")
    op.drop_index("ix_events_subject", table_name="events")
    op.drop_index("ix_events_occurred_at", table_name="events")
    op.drop_index("ix_events_actor_occurred_at", table_name="events")
    op.drop_table("events")
