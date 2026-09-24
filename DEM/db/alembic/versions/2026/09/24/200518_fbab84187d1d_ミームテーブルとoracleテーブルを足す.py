"""ミームテーブルとoracleテーブルを足す

Revision ID: fbab84187d1d
Revises: 56c6bd7ffe26
Create Date: 2026-09-24 20:05:18.896779

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbab84187d1d'
down_revision: Union[str, Sequence[str], None] = '56c6bd7ffe26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MEME_SEEDED_COMMENT = 'ミームを抜き出し済みか。false に戻すと、次の抽出で抜き出し直す'
_DIRECTORY_PATH_COMMENT = ('import,export時の配置先。worlds/{table}/ からの相対ディレクトリパス。'
                           '空ならテーブル直下に置く')
_FILENAME_COMMENT = ('import,export時のファイル名(id・拡張子を除いた部分)。'
                     '空なら {id}.md。テーブルが持つ name 等の列とは別物')


def upgrade() -> None:
    """語(term)・oracle(著者の覚え書き)・人物の筋書きから抜き出す、ミーム(meme)テーブルを足す。

    oracle は元から worlds/oracle/ に手書きの md として存在するので、md 化した表(MarkdownBase)として足す。
    """
    op.create_table('meme',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('text', sa.String(), nullable=False, comment='ミーム'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('oracle',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('meme_seeded', sa.Boolean(), nullable=False, server_default=sa.false(), comment=_MEME_SEEDED_COMMENT),
    sa.Column('text', sa.String(), nullable=False),
    sa.Column('directory_path', sa.String(), nullable=True, comment=_DIRECTORY_PATH_COMMENT),
    sa.Column('filename', sa.String(), nullable=True, comment=_FILENAME_COMMENT),
    sa.PrimaryKeyConstraint('id')
    )
    for table in ('term', 'character'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('meme_seeded', sa.Boolean(), nullable=False,
                                          server_default=sa.false(), comment=_MEME_SEEDED_COMMENT))


def downgrade() -> None:
    """Downgrade schema."""
    for table in ('term', 'character'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('meme_seeded')
    op.drop_table('oracle')
    op.drop_table('meme')
