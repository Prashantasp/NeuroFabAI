"""production hardening: tenancy, pipeline, chat persistence

Hand-adjusted from autogenerate. The parts autogenerate cannot infer:

* PostgreSQL native ENUM -> VARCHAR conversions need an explicit ``USING`` cast,
  and the now-unused enum types must be dropped afterwards. Status values are
  stored as strings so adding a new pipeline stage no longer requires
  ``ALTER TYPE ... ADD VALUE`` (which cannot run inside a transaction).
* ``users.last_login`` was a VARCHAR holding ISO timestamps; it needs a cast.
* Backfills for the new NOT NULL columns must run before the constraint.

Revision ID: bda228b5224c
Revises: 5a9b816d1c75
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bda228b5224c"
down_revision: Union[str, None] = "5a9b816d1c75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DOCUMENT_STATUSES = (
    "UPLOADING", "QUEUED", "VALIDATING", "TEXT_EXTRACTION", "CHUNKING",
    "EMBEDDING", "VECTOR_INDEXING", "KNOWLEDGE_GRAPH", "READY", "FAILED", "ARCHIVED",
)
# Stages that existed in earlier prototypes and no longer do. Anything sitting in
# one of these is remapped so no row is left holding an unrepresentable value.
LEGACY_STATUS_MAP = {
    "UPLOADED": "QUEUED",
    "PROCESSING": "VALIDATING",
    "PARSING": "TEXT_EXTRACTION",
    "ENTITY_EXTRACTION": "KNOWLEDGE_GRAPH",
    "GRAPH_CONSTRUCTION": "KNOWLEDGE_GRAPH",
    "GRAPH_GENERATION": "KNOWLEDGE_GRAPH",
    "INDEXING": "VECTOR_INDEXING",
}


def _enum_to_varchar(table: str, column: str, length: int, enum_name: str) -> None:
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT"
    )
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN {column} "
        f"TYPE VARCHAR({length}) USING {column}::text"
    )
    op.execute(f"DROP TYPE IF EXISTS {enum_name}")


def upgrade() -> None:
    # ---------------------------------------------------------------- users
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.alter_column("users", "full_name", type_=sa.String(length=120), existing_nullable=True)
    op.alter_column("users", "company", type_=sa.String(length=120), existing_nullable=True)
    op.alter_column("users", "avatar_url", type_=sa.String(length=512), existing_nullable=True)

    # last_login held ISO-8601 strings; convert in place.
    op.execute(
        "ALTER TABLE users ALTER COLUMN last_login "
        "TYPE TIMESTAMPTZ USING NULLIF(last_login, '')::timestamptz"
    )
    _enum_to_varchar("users", "role", 32, "userrole")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'ENGINEER'")

    # ----------------------------------------------------------- workspaces
    op.alter_column("workspaces", "name", type_=sa.String(length=120), existing_nullable=False)
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])

    _enum_to_varchar("workspace_members", "role", 32, "workspacememberrole")
    op.execute("ALTER TABLE workspace_members ALTER COLUMN role SET DEFAULT 'MEMBER'")
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    # ------------------------------------------------------------ documents
    op.add_column("documents", sa.Column("summary", sa.String(length=2048), nullable=True))
    for column in ("chunk_count", "entity_count", "relationship_count", "retry_count"):
        op.add_column(
            "documents",
            sa.Column(column, sa.Integer(), nullable=False, server_default="0"),
        )

    # Convert before remapping: a fresh upgrade may have added enum values in
    # the same transaction, and PostgreSQL forbids using them until commit.
    _enum_to_varchar("documents", "status", 32, "documentstatus")
    for old, new in LEGACY_STATUS_MAP.items():
        op.execute(f"UPDATE documents SET status = '{new}' WHERE status = '{old}'")
    _enum_to_varchar("documents", "embedding_status", 32, "embeddingstatus")
    _enum_to_varchar("documents", "graph_status", 32, "graphstatus")
    op.execute("ALTER TABLE documents ALTER COLUMN status SET DEFAULT 'UPLOADING'")
    op.execute("ALTER TABLE documents ALTER COLUMN embedding_status SET DEFAULT 'PENDING'")
    op.execute("ALTER TABLE documents ALTER COLUMN graph_status SET DEFAULT 'PENDING'")

    op.alter_column(
        "documents", "workspace_id", existing_type=sa.String(length=36), nullable=False
    )
    op.alter_column(
        "documents", "owner_id", existing_type=sa.String(length=36), nullable=False
    )

    # Both FKs previously used ON DELETE SET NULL against NOT NULL columns, so
    # deleting a user or workspace would fail outright. Documents are owned by a
    # workspace and a user, so they cascade with either.
    op.drop_constraint("documents_owner_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key(
        "documents_owner_id_fkey", "documents", "users", ["owner_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint("documents_workspace_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key(
        "documents_workspace_id_fkey",
        "documents",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index("ix_documents_uploaded_at", "documents", ["uploaded_at"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_workspace_uploaded", "documents", ["workspace_id", "uploaded_at"])
    op.create_index("ix_documents_workspace_status", "documents", ["workspace_id", "status"])
    op.create_unique_constraint(
        "uq_documents_workspace_checksum", "documents", ["workspace_id", "checksum"]
    )

    op.create_unique_constraint(
        "uq_document_versions_doc_version", "document_versions", ["document_id", "version"]
    )

    # --------------------------------------------------- conversations/chat
    op.add_column(
        "conversations",
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="general"),
    )
    # A conversation with no workspace cannot be scoped to a tenant, so the
    # column becomes required. Orphans are removed first (this table has never
    # been written to by the application).
    op.execute("DELETE FROM conversations WHERE workspace_id IS NULL")
    op.alter_column(
        "conversations", "workspace_id", existing_type=sa.String(length=36), nullable=False
    )
    op.drop_constraint("conversations_workspace_id_fkey", "conversations", type_="foreignkey")
    op.create_foreign_key(
        "conversations_workspace_id_fkey",
        "conversations",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_conversations_workspace_user_updated",
        "conversations",
        ["workspace_id", "user_id", "updated_at"],
    )

    # JSONB, matching JSONType's PostgreSQL variant: binary storage, indexable,
    # and no re-parsing on read.
    op.add_column(
        "messages",
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("messages", sa.Column("error", sa.Text(), nullable=True))
    op.execute("UPDATE messages SET citations = '[]'::json WHERE citations IS NULL")
    op.alter_column("messages", "citations", existing_type=sa.JSON(), nullable=False)
    op.alter_column("messages", "role", type_=sa.String(length=16), existing_nullable=False)

    # Server defaults were only needed to backfill existing rows; the ORM
    # supplies these values on insert from here on.
    for table, column in (
        ("users", "failed_login_attempts"),
        ("documents", "chunk_count"),
        ("documents", "entity_count"),
        ("documents", "relationship_count"),
        ("documents", "retry_count"),
        ("conversations", "mode"),
        ("messages", "payload"),
    ):
        op.alter_column(table, column, server_default=None)


def downgrade() -> None:
    op.alter_column("messages", "role", type_=sa.String(length=50), existing_nullable=False)
    op.alter_column("messages", "citations", existing_type=sa.JSON(), nullable=True)
    op.drop_column("messages", "error")
    op.drop_column("messages", "payload")

    op.drop_index("ix_conversations_workspace_user_updated", table_name="conversations")
    op.drop_constraint("conversations_workspace_id_fkey", "conversations", type_="foreignkey")
    op.create_foreign_key(
        "conversations_workspace_id_fkey",
        "conversations",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "conversations", "workspace_id", existing_type=sa.String(length=36), nullable=True
    )
    op.drop_column("conversations", "mode")

    op.drop_constraint("uq_document_versions_doc_version", "document_versions", type_="unique")
    op.drop_constraint("uq_documents_workspace_checksum", "documents", type_="unique")
    op.drop_index("ix_documents_workspace_status", table_name="documents")
    op.drop_index("ix_documents_workspace_uploaded", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_uploaded_at", table_name="documents")

    op.drop_constraint("documents_owner_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key(
        "documents_owner_id_fkey", "documents", "users", ["owner_id"], ["id"], ondelete="SET NULL"
    )
    op.drop_constraint("documents_workspace_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key(
        "documents_workspace_id_fkey",
        "documents",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for column in ("retry_count", "relationship_count", "entity_count", "chunk_count", "summary"):
        op.drop_column("documents", column)

    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_index("ix_workspaces_owner_id", table_name="workspaces")

    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
    op.execute("ALTER TABLE users ALTER COLUMN last_login TYPE VARCHAR USING last_login::text")

    # Enum types are intentionally not recreated: the VARCHAR columns hold the
    # same values and re-deriving the historical enum members is not meaningful.
