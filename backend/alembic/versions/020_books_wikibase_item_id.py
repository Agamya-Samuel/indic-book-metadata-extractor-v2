"""Record the Wikibase item created for a book.

Revision ID: 020
Revises: 019
Create Date: 2026-11-18

Publishing a book to Wikibase is idempotent: once ``books.wikibase_item_id``
holds the item id, later runs update that item instead of creating duplicates.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("books", sa.Column("wikibase_item_id", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "wikibase_item_id")