"""ミームに分類を足す

Revision ID: 4d2c1cf285c0
Revises: e1c9532b3315
Create Date: 2026-09-24 23:29:48.949595

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d2c1cf285c0'
down_revision: Union[str, Sequence[str], None] = 'e1c9532b3315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """ミームに分類(category)を足す。既にあるミームは空のまま残し、次の抽出で AI が振る。"""
    with op.batch_alter_table('meme', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(), nullable=True, comment='分類。信条/欲求/境遇/集団/理 のいずれか。空なら次の抽出で AI が振る'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('meme', schema=None) as batch_op:
        batch_op.drop_column('category')
