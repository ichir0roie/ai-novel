"""出来事にミームの抜き出し済みフラグを足す

Revision ID: 7c1f74484959
Revises: 4d2c1cf285c0
Create Date: 2026-09-24 23:37:23.583365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1f74484959'
down_revision: Union[str, Sequence[str], None] = '4d2c1cf285c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """出来事(event)をミームの抜き出し元に足す。既にある出来事は未抽出(false)として、次の抽出で抜き出す。"""
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('meme_seeded', sa.Boolean(), nullable=False, server_default=sa.false(),
                                      comment='ミームを抜き出し済みか。false に戻すと、次の抽出で抜き出し直す'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_column('meme_seeded')
