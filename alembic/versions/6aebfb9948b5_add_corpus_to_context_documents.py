"""add corpus to context documents

Revision ID: 6aebfb9948b5
Revises: 3618b1d7fdbc
Create Date: 2026-04-02 15:34:57.046869

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6aebfb9948b5'
down_revision: Union[str, Sequence[str], None] = '3618b1d7fdbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "context_documents",
        sa.Column("corpus", sa.String(length=30), nullable=True),
    )
    op.create_index(
        op.f("ix_context_documents_corpus"),
        "context_documents",
        ["corpus"],
        unique=False,
    )

    op.execute("UPDATE context_documents SET corpus = 'us_fda' WHERE corpus IS NULL")

    op.alter_column("context_documents", "corpus", nullable=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_context_documents_corpus"), table_name="context_documents")
    op.drop_column("context_documents", "corpus")
