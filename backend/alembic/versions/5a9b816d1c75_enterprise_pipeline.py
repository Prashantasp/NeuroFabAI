"""enterprise_pipeline

Revision ID: 5a9b816d1c75
Revises: 3a9a816d1c74
Create Date: 2026-07-24 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5a9b816d1c75'
down_revision = '3a9a816d1c74'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add new statuses to DocumentStatus enum
    op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'VALIDATING'")
    op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'TEXT_EXTRACTION'")
    op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'VECTOR_INDEXING'")
    op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'KNOWLEDGE_GRAPH'")

    # Add pipeline tracking fields to documents
    op.add_column('documents', sa.Column('current_stage', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('progress_percentage', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('documents', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documents', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documents', sa.Column('failure_reason', sa.String(), nullable=True))

    # Add storage path to document versions
    op.add_column('document_versions', sa.Column('storage_path', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('document_versions', 'storage_path')
    op.drop_column('documents', 'failure_reason')
    op.drop_column('documents', 'completed_at')
    op.drop_column('documents', 'started_at')
    op.drop_column('documents', 'progress_percentage')
    op.drop_column('documents', 'current_stage')
