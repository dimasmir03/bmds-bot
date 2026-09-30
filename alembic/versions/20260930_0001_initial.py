"""Initial users and image jobs tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260930_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    job_status = postgresql.ENUM(
        "PENDING",
        "QUEUED",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        name="job_status",
        create_type=False,
    )
    job_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("telegram_user_id", name=op.f("uq_users_telegram_user_id")),
    )
    op.create_index(op.f("ix_users_telegram_user_id"), "users", ["telegram_user_id"])
    op.create_table(
        "image_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("input_file_path", sa.String(length=1024), nullable=False),
        sa.Column("output_file_path", sa.String(length=1024), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("parent_job_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_job_id"],
            ["image_jobs.id"],
            name=op.f("fk_image_jobs_parent_job_id_image_jobs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_image_jobs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_jobs")),
    )
    op.create_index(op.f("ix_image_jobs_created_at"), "image_jobs", ["created_at"])
    op.create_index(op.f("ix_image_jobs_parent_job_id"), "image_jobs", ["parent_job_id"])
    op.create_index(op.f("ix_image_jobs_status"), "image_jobs", ["status"])
    op.create_index(op.f("ix_image_jobs_user_id"), "image_jobs", ["user_id"])


def downgrade() -> None:
    op.drop_table("image_jobs")
    op.drop_table("users")
    postgresql.ENUM(name="job_status").drop(op.get_bind(), checkfirst=True)
