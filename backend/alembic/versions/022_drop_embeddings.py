"""Drop the unused embeddings table and the pgvector extension.

Revision ID: 022
Revises: 021
Create Date: 2026-11-20

``embeddings`` and the ``vector`` extension were provisioned in 001 for a
semantic-search feature that was never built. No service ever wrote to or read
from the table, so both are dropped. Both statements are guarded with
``IF EXISTS`` so the revision is a no-op on a database created after 001 was
rewritten to stop creating them, and still cleans up an older database.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")


def downgrade() -> None:
    # The vector extension and its Python bindings have been removed, so the
    # table cannot be recreated. Downgrading past 022 leaves the schema without
    # it, which matches current HEAD.
    pass
