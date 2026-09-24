"""アイデアとミームに検証の節を足す

Revision ID: 06537c9aa09c
Revises: 7c1f74484959
Create Date: 2026-09-24 18:35:37.807086

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06537c9aa09c'
down_revision: Union[str, Sequence[str], None] = '7c1f74484959'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """アイデア(idea)とミーム(meme)に検証の節(review)を足す。既にあるものは空のまま残し、検める入口で埋める。"""
    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.add_column(sa.Column('review', sa.String(), nullable=True, comment='AI がネット検索で検めた妥当性と補足。空ならまだ検めていない'))

    with op.batch_alter_table('meme', schema=None) as batch_op:
        batch_op.add_column(sa.Column('review', sa.String(), nullable=True, comment='AI がネット検索で検めた妥当性と補足。空ならまだ検めていない'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('meme', schema=None) as batch_op:
        batch_op.drop_column('review')

    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.drop_column('review')
