"""Add workspace_extensions

Revision ID: 3a9a816d1c74
Revises: 49f1550d4c5d
Create Date: 2026-07-24 03:49:24.475459

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3a9a816d1c74'
down_revision: Union[str, None] = '49f1550d4c5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update users table
    op.add_column('users', sa.Column('last_workspace_id', sa.String(length=36), nullable=True))

    # 2. Update Documents table (Add missing enum values using raw SQL on Postgres, add columns)
    
    # In PostgreSQL, we can't easily alter enum values in a single cross-platform way, 
    # but we can add the new values if we were connected. 
    # Since this is an initial un-run migration anyway, I will just add the columns.
    op.add_column('documents', sa.Column('title', sa.String(), nullable=False, server_default='Untitled'))
    op.add_column('documents', sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('documents', sa.Column('mime_type', sa.String(), nullable=False, server_default='application/pdf'))
    op.add_column('documents', sa.Column('checksum', sa.String(length=64), nullable=False, server_default=''))
    op.add_column('documents', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('documents', sa.Column('page_count', sa.Integer(), nullable=True))
    
    # Note: Enum changes (ARCHIVED, EmbeddingStatus, GraphStatus) would require raw type creation in PG.
    op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'ARCHIVED'")
    op.execute("CREATE TYPE embeddingstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')")
    op.execute("CREATE TYPE graphstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')")
    
    op.add_column('documents', sa.Column('embedding_status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', name='embeddingstatus'), nullable=False, server_default='PENDING'))
    op.add_column('documents', sa.Column('graph_status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', name='graphstatus'), nullable=False, server_default='PENDING'))

    op.create_index(op.f('ix_documents_title'), 'documents', ['title'], unique=False)
    op.create_index(op.f('ix_documents_checksum'), 'documents', ['checksum'], unique=False)
    
    # 3. Create DocumentVersions table
    op.create_table(
        'document_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('document_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.Column('uploaded_by', sa.String(length=36), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_versions_id'), 'document_versions', ['id'], unique=False)
    op.create_index(op.f('ix_document_versions_document_id'), 'document_versions', ['document_id'], unique=False)

    # 4. Create AuditLogs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('workspace_id', sa.String(length=36), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=36), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('request_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_request_id'), 'audit_logs', ['request_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_workspace_id'), 'audit_logs', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('document_versions')
    
    op.drop_column('documents', 'graph_status')
    op.drop_column('documents', 'embedding_status')
    op.execute("DROP TYPE graphstatus")
    op.execute("DROP TYPE embeddingstatus")
    
    op.drop_index(op.f('ix_documents_checksum'), table_name='documents')
    op.drop_index(op.f('ix_documents_title'), table_name='documents')
    op.drop_column('documents', 'page_count')
    op.drop_column('documents', 'version')
    op.drop_column('documents', 'checksum')
    op.drop_column('documents', 'mime_type')
    op.drop_column('documents', 'file_size')
    op.drop_column('documents', 'title')
    
    op.drop_column('users', 'last_workspace_id')
