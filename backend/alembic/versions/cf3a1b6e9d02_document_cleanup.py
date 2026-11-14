"""Durable document deletion outbox.

Revision ID: cf3a1b6e9d02
Revises: bda228b5224c
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "cf3a1b6e9d02"
down_revision = "bda228b5224c"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "document_cleanup",
        sa.Column("document_id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("file_paths", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_cleanup_workspace_id", "document_cleanup", ["workspace_id"])


def downgrade():
    op.drop_table("document_cleanup")
