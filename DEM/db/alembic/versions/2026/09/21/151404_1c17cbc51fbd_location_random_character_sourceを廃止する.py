"""location_random_character_sourceを廃止する

Revision ID: 1c17cbc51fbd
Revises: 7b15d02a4ecd
Create Date: 2026-09-21 15:14:04.181926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c17cbc51fbd'
down_revision: Union[str, Sequence[str], None] = '7b15d02a4ecd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.drop_column('random_character_source')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'random_character_source', sa.BOOLEAN(), nullable=False,
            server_default=sa.false(),
            comment='オンなら、この場所にまだ人物が一人も居ないとき、月初の判定でまとめて1〜4人を生成する対象にする(DEM/local_ai/time_keeper/random_character_generator.py の seed_initial_characters)。長期間、場所ごとの人物が増えない問題への対処'))
