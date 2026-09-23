"""人物相関にstart_endを足す

Revision ID: bacc670e4a5f
Revises: c3a1f0d2b4e6
Create Date: 2026-09-23 09:15:08.650966

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bacc670e4a5f'
down_revision: Union[str, Sequence[str], None] = 'c3a1f0d2b4e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('character_relation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('start', sa.BigInteger(), nullable=True, comment='この関係が始まる時。空なら初めから'))
        batch_op.add_column(sa.Column('end', sa.BigInteger(), nullable=True, comment='この関係が終わる時。空なら続いている'))



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('character_relation', schema=None) as batch_op:
        batch_op.drop_column('end')
        batch_op.drop_column('start')

