"""人物のsub_characterをmain_characterへ反転

Revision ID: 82c20d8db0c5
Revises: 24327ee59e1c
Create Date: 2026-09-24 07:35:11.410798

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82c20d8db0c5'
down_revision: Union[str, Sequence[str], None] = '24327ee59e1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MAIN_COMMENT = 'メインキャラクターか。出来事・筋書きのランダム生成は、この列が false(サブキャラクター)の人物・対象だけを対象にする'
_SUB_COMMENT = 'メインキャラクター以外のサブキャラクターか。出来事・筋書きのランダム生成は、この列が true の人物・対象だけを対象にする'


def upgrade() -> None:
    """sub_character を反転して main_character へ移す。既定値が false のまま、新しく足す人物はサブキャラクターになる。"""
    with op.batch_alter_table('character', schema=None) as batch_op:
        batch_op.add_column(sa.Column('main_character', sa.Boolean(), nullable=False,
                                      server_default=sa.false(), comment=_MAIN_COMMENT))
    op.execute('UPDATE "character" SET main_character = NOT sub_character')
    with op.batch_alter_table('character', schema=None) as batch_op:
        batch_op.drop_column('sub_character')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('character', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sub_character', sa.Boolean(), nullable=False,
                                      server_default=sa.false(), comment=_SUB_COMMENT))
    op.execute('UPDATE "character" SET sub_character = NOT main_character')
    with op.batch_alter_table('character', schema=None) as batch_op:
        batch_op.drop_column('main_character')
