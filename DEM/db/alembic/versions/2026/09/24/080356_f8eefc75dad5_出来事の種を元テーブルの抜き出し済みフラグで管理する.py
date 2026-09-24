"""出来事の種を元テーブルの抜き出し済みフラグで管理する

Revision ID: f8eefc75dad5
Revises: 76fbe5ec1c2e
Create Date: 2026-09-24 08:03:56.236362

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8eefc75dad5'
down_revision: Union[str, Sequence[str], None] = '76fbe5ec1c2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SEEDED_TABLES = ("story", "episode", "character", "event")
_SEEDED_COMMENT = '出来事の種を抜き出し済みか。false に戻すと、次の毎日のルーチンで抜き出し直す'
_HASH_COMMENT = '種を抜き出した本文の sha256。本文と食い違ったら抜き出し直す'


def _replace_event_seed(columns: list[sa.Column], copied: str) -> None:
    """event_seed を `columns` の形で張り直す。名前の無い外部キーは batch で落とせないため。"""
    op.create_table('_event_seed_new', sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
                    *columns, sa.PrimaryKeyConstraint('id'))
    op.execute(f'INSERT INTO _event_seed_new (id, {copied}) SELECT id, {copied} FROM event_seed')
    op.drop_table('event_seed')
    op.rename_table('_event_seed_new', 'event_seed')


def upgrade() -> None:
    """抜き出した元を、元の表の event_seeded で持つ。種はそのまま残す。"""
    for table in _SEEDED_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('event_seeded', sa.Boolean(), nullable=False,
                                          server_default=sa.false(), comment=_SEEDED_COMMENT))
        op.execute(f'UPDATE "{table}" SET event_seeded = 1 '
                   f'WHERE id IN (SELECT {table}_id FROM event_seed_source WHERE {table}_id IS NOT NULL)')
    _replace_event_seed([sa.Column('text', sa.String(), nullable=False, comment='種')], 'text')
    op.drop_table('event_seed_source')


def downgrade() -> None:
    """種がどの元から来たかは残っていないので、種は捨てて抜き出し直させる。"""
    op.create_table(
        'event_seed_source',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        *(sa.Column(f'{table}_id', sa.Integer(), sa.ForeignKey(f'{table}.id'), unique=True, nullable=True)
          for table in _SEEDED_TABLES),
        sa.Column('source_hash', sa.String(), nullable=False, comment=_HASH_COMMENT),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute('DELETE FROM event_seed')
    _replace_event_seed([
        sa.Column('event_seed_source_id', sa.Integer(), sa.ForeignKey('event_seed_source.id'), nullable=False),
        sa.Column('text', sa.String(), nullable=False, comment='種'),
    ], 'text')
    op.create_index('ix_event_seed_event_seed_source_id', 'event_seed', ['event_seed_source_id'])
    for table in _SEEDED_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('event_seeded')
