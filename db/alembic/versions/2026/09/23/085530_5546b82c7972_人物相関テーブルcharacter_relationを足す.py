"""人物相関テーブルcharacter_relationを足す

Revision ID: 5546b82c7972
Revises: 796c5ab097d4
Create Date: 2026-09-23 08:55:30.018326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5546b82c7972'
down_revision: Union[str, Sequence[str], None] = '796c5ab097d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('character_relation',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('character_id_1', sa.Integer(), nullable=False, comment='関係の主体となる人物'),
    sa.Column('character_id_2', sa.Integer(), nullable=False, comment='関係の相手となる人物'),
    sa.Column('relation', sa.String(), nullable=False, comment='関係の短い名前(母・師・宿敵 など)'),
    sa.Column('text', sa.String(), nullable=False),
    sa.Column('directory_path', sa.String(), nullable=True, comment='import,export時の配置先。worlds/{table}/ からの相対ディレクトリパス。空ならテーブル直下に置く'),
    sa.Column('filename', sa.String(), nullable=True, comment='import,export時のファイル名(id・拡張子を除いた部分)。空なら {id}.md。テーブルが持つ name 等の列とは別物'),
    sa.ForeignKeyConstraint(['character_id_1'], ['character.id'], ),
    sa.ForeignKeyConstraint(['character_id_2'], ['character.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('character_relation', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_character_relation_character_id_1'), ['character_id_1'], unique=False)
        batch_op.create_index(batch_op.f('ix_character_relation_character_id_2'), ['character_id_2'], unique=False)



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('character_relation', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_character_relation_character_id_2'))
        batch_op.drop_index(batch_op.f('ix_character_relation_character_id_1'))

    op.drop_table('character_relation')
