"""filepath列をtag列に置き換える

Revision ID: 404d6a1bf8d5
Revises: 88bc0ba4177e
Create Date: 2026-09-20 20:42:29.394534

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '404d6a1bf8d5'
down_revision: Union[str, Sequence[str], None] = '88bc0ba4177e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    'character', 'character_drive', 'episode', 'event', 'location',
    'location_resource', 'object', 'plot', 'skill', 'story', 'term',
)


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                'filepath', new_column_name='tag', existing_type=sa.String(),
                existing_nullable=True, comment='import,export時のファイル名用')


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                'tag', new_column_name='filepath', existing_type=sa.String(),
                existing_nullable=True, existing_comment='import,export時のファイル名用',
                comment=None)
