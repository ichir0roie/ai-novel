"""アイデアとミームに検証の節を足す

Revision ID: 0ca6fda25c60
Revises: f3edb83aaeaf
Create Date: 2026-09-24 18:44:40.090019

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ca6fda25c60'
down_revision: Union[str, Sequence[str], None] = 'f3edb83aaeaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """アイデア(idea)とミーム(meme)に検証の節(fact_check)を足す。既にあるものは空のまま残し、検める入口で埋める。"""
    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fact_check', sa.String(), nullable=True, comment='AI が Dラボ・ネット検索で検めた妥当性と補足。空ならまだ検めていない'))

    with op.batch_alter_table('meme', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fact_check', sa.String(), nullable=True, comment='AI が Dラボ・ネット検索で検めた妥当性と補足。空ならまだ検めていない'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('meme', schema=None) as batch_op:
        batch_op.drop_column('fact_check')

    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.drop_column('fact_check')
