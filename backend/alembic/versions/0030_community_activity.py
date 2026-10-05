"""Store Discord message events, voice samples and scoped ingestion credentials.

Revision ID: 0030
Revises: 0029
"""

import sqlalchemy as sa

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_events",
        sa.Column("guild_id", sa.String(20), primary_key=True),
        sa.Column("message_id", sa.String(20), primary_key=True),
        sa.Column("user_id", sa.String(20), nullable=False),
        sa.Column("channel_id", sa.String(20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reply_to_user_id", sa.String(20), nullable=True),
        sa.Column("text_length", sa.Integer(), nullable=False),
        sa.Column("attachment_count", sa.Integer(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("text_length >= 0", name="ck_message_text_length"),
        sa.CheckConstraint("attachment_count >= 0", name="ck_message_attachment_count"),
    )
    op.create_index(
        "ix_message_events_guild_time", "message_events", ["guild_id", "sent_at"]
    )
    op.create_index(
        "ix_message_events_guild_user_time",
        "message_events",
        ["guild_id", "user_id", "sent_at"],
    )
    op.create_index(
        "ix_message_events_guild_channel_time",
        "message_events",
        ["guild_id", "channel_id", "sent_at"],
    )
    op.create_table(
        "voice_samples",
        sa.Column("guild_id", sa.String(20), primary_key=True),
        sa.Column("user_id", sa.String(20), primary_key=True),
        sa.Column("sampled_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("channel_id", sa.String(20), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_voice_samples_guild_time", "voice_samples", ["guild_id", "sampled_at"]
    )
    op.create_index(
        "ix_voice_samples_guild_channel_time",
        "voice_samples",
        ["guild_id", "channel_id", "sampled_at"],
    )
    op.create_table(
        "activity_ingest_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("guild_id", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("activity_ingest_tokens")
    op.drop_table("voice_samples")
    op.drop_table("message_events")
