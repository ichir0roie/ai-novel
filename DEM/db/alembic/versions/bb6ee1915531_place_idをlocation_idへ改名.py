"""character_place object_place の place_id を location_id へ改名

Revision ID: bb6ee1915531
Revises: 13361519c72b
Create Date: 2026-09-19 15:05:03.994947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb6ee1915531'
down_revision: Union[str, Sequence[str], None] = '13361519c72b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('character_place', schema=None) as batch_op:
        batch_op.alter_column('place_id', new_column_name='location_id',
                               existing_type=sa.Integer())

    with op.batch_alter_table('object_place', schema=None) as batch_op:
        batch_op.alter_column('place_id', new_column_name='location_id',
                               existing_type=sa.Integer())


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('object_place', schema=None) as batch_op:
        batch_op.alter_column('location_id', new_column_name='place_id',
                               existing_type=sa.Integer())

    with op.batch_alter_table('character_place', schema=None) as batch_op:
        batch_op.alter_column('location_id', new_column_name='place_id',
                               existing_type=sa.Integer())
