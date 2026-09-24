"""出来事の種の元を元テーブルごとのid列にする

Revision ID: 76fbe5ec1c2e
Revises: cd51e8d34592
Create Date: 2026-09-24 07:56:43.334366

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76fbe5ec1c2e'
down_revision: Union[str, Sequence[str], None] = 'cd51e8d34592'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 元の種類ごとに持たせる id の列と、旧来の source の値。
_SOURCES = (("story_id", "story", "作品の本文から"),
            ("episode_id", "episode", "話の種(key)から。無ければ本文から"),
            ("character_id", "character", "人物の text の # plot の節から"),
            ("event_id", "event", "出来事の本文から"))
_HASH_COMMENT = '種を抜き出した本文の sha256。本文と食い違ったら抜き出し直す'


def upgrade() -> None:
    """(source, source_id) を元のテーブルごとの id 列に分ける。

    旧来の表は名前の無い UNIQUE(source, source_id) を持ち、batch では落とせないので、
    新しい形の表を作って行を移し、差し替える。
    """
    op.create_table(
        '_event_seed_source_new',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        *(sa.Column(column, sa.Integer(), sa.ForeignKey(f'{table}.id'), unique=True, nullable=True,
                    comment=comment)
          for column, table, comment in _SOURCES),
        sa.Column('source_hash', sa.String(), nullable=False, comment=_HASH_COMMENT),
        sa.PrimaryKeyConstraint('id'),
    )
    columns = ", ".join(column for column, _, _ in _SOURCES)
    picks = ", ".join(f"CASE WHEN source = '{table}' THEN source_id END" for _, table, _ in _SOURCES)
    op.execute(f'INSERT INTO _event_seed_source_new (id, {columns}, source_hash) '
               f'SELECT id, {picks}, source_hash FROM event_seed_source')
    op.drop_table('event_seed_source')
    op.rename_table('_event_seed_source_new', 'event_seed_source')


def downgrade() -> None:
    """出来事(event_id)から抜き出した種は、旧来の source に無い種類なので捨てる。"""
    op.execute('DELETE FROM event_seed WHERE event_seed_source_id IN '
               '(SELECT id FROM event_seed_source WHERE event_id IS NOT NULL)')
    op.create_table(
        '_event_seed_source_old',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(), nullable=False, comment='元の種類。story / episode / character'),
        sa.Column('source_id', sa.Integer(), nullable=False, comment='元のレコードの id'),
        sa.Column('source_hash', sa.String(), nullable=False, comment=_HASH_COMMENT),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_id'),
    )
    kept = _SOURCES[:3]
    source = "CASE " + " ".join(f"WHEN {column} IS NOT NULL THEN '{table}'" for column, table, _ in kept) + " END"
    source_id = "COALESCE(" + ", ".join(column for column, _, _ in kept) + ")"
    op.execute(f'INSERT INTO _event_seed_source_old (id, source, source_id, source_hash) '
               f'SELECT id, {source}, {source_id}, source_hash FROM event_seed_source WHERE event_id IS NULL')
    op.drop_table('event_seed_source')
    op.rename_table('_event_seed_source_old', 'event_seed_source')
