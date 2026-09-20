"""event_の_place_id_を_location_id_へ改名

Revision ID: b7edc9a5acc3
Revises: a1a40ed2dc0d
Create Date: 2026-09-20 18:37:40.749006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7edc9a5acc3'
down_revision: Union[str, Sequence[str], None] = 'a1a40ed2dc0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.alter_column('place_id', new_column_name='location_id',
                               existing_type=sa.Integer())


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.alter_column('location_id', new_column_name='place_id',
                               existing_type=sa.Integer())
