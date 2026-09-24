"""場所に輪郭polygonを足す

Revision ID: c3a1f0d2b4e6
Revises: 5546b82c7972
Create Date: 2026-09-23 08:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a1f0d2b4e6'
down_revision: Union[str, Sequence[str], None] = '5546b82c7972'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'polygon', sa.JSON(), nullable=True,
            comment='輪郭。GeoJSON の Polygon(`coordinates` は [経度, 緯度] の環の並び、先頭が外周で以降は穴)。地図では面として描く。経緯度が無くても持てる'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.drop_column('polygon')
