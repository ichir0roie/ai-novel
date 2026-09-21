"""root_place_name_born_place_idを廃止する

Revision ID: 7b15d02a4ecd
Revises: f5dec0a954e7
Create Date: 2026-09-21 15:04:13.538615

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b15d02a4ecd'
down_revision: Union[str, Sequence[str], None] = 'f5dec0a954e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('character', schema=None) as batch_op:
        batch_op.drop_column('root_place_name')
        batch_op.drop_column('born_place_id')

    with op.batch_alter_table('object', schema=None) as batch_op:
        batch_op.drop_column('root_place_name')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('object', schema=None) as batch_op:
        batch_op.add_column(sa.Column('root_place_name', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(None, 'location', ['root_place_name'], ['id'])

    with op.batch_alter_table('character', schema=None) as batch_op:
        batch_op.add_column(sa.Column('born_place_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('root_place_name', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(None, 'location', ['born_place_id'], ['id'])
        batch_op.create_foreign_key(None, 'location', ['root_place_name'], ['id'])
