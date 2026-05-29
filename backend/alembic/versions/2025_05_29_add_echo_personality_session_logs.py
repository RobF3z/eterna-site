"""2025-05-29_add_echo_personality_session_logs

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-05-29

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # echoes — one per creator (MVP)
    op.create_table(
        "echoes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("creator_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", name="uq_echoes_creator_id"),
    )
    op.create_index("ix_echoes_creator_id", "echoes", ["creator_id"], unique=True)

    # user_personality — three MVP fields
    op.create_table(
        "user_personality",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("traits", sa.Text(), server_default="", nullable=False),
        sa.Column("tone", sa.Text(), server_default="warm", nullable=False),
        sa.Column("catchphrases", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_personality_user_id"),
    )
    op.create_index("ix_user_personality_user_id", "user_personality", ["user_id"], unique=True)

    # session_logs — AMA chat history per Echo per viewer
    op.create_table(
        "session_logs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("echo_id", UUID(as_uuid=True), nullable=False),
        sa.Column("viewer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["echo_id"], ["echoes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["viewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_logs_echo_id", "session_logs", ["echo_id"])
    op.create_index("ix_session_logs_viewer_id", "session_logs", ["viewer_id"])


def downgrade() -> None:
    op.drop_index("ix_session_logs_viewer_id", table_name="session_logs")
    op.drop_index("ix_session_logs_echo_id", table_name="session_logs")
    op.drop_table("session_logs")

    op.drop_index("ix_user_personality_user_id", table_name="user_personality")
    op.drop_table("user_personality")

    op.drop_index("ix_echoes_creator_id", table_name="echoes")
    op.drop_table("echoes")
