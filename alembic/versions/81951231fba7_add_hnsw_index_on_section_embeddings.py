"""add hnsw index on section embeddings

Revision ID: 81951231fba7
Revises: 4ee563ba8b97
Create Date: 2026-04-02 11:57:45.386822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81951231fba7'
down_revision: Union[str, Sequence[str], None] = '4ee563ba8b97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sections_embedding
        ON regulation_sections
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sections_embedding")
