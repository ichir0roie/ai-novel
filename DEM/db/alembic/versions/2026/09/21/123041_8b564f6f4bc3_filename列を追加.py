"""filename列を追加

directory_path は元は filepath(→tag)から名前を引き継いだ列で、
「import,export時のファイル名用」という古い役目のデータを一部
(plot テーブルの一部の行)にまだ持ったままだった。ここで本来の
ファイル名用の列 filename を新設し、directory_path に残っていた
その古いデータを filename へ移してから、directory_path 側は
本来の(ディレクトリだけの)意味に空にする。

Revision ID: 8b564f6f4bc3
Revises: ce022c39f4f4
Create Date: 2026-09-21 12:30:41.848929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b564f6f4bc3'
down_revision: Union[str, Sequence[str], None] = 'ce022c39f4f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    'character', 'character_drive', 'episode', 'event', 'location',
    'location_resource', 'object', 'plot', 'story', 'term',
)

COMMENT = (
    'import,export時のファイル名(id・拡張子を除いた部分)。'
    '空なら {id}.md。テーブルが持つ name 等の列とは別物'
)


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('filename', sa.String(), nullable=True, comment=COMMENT))

    for table in TABLES:
        op.execute(
            f"UPDATE {table} SET filename = directory_path, directory_path = NULL "
            "WHERE directory_path IS NOT NULL AND directory_path != ''"
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        op.execute(
            f"UPDATE {table} SET directory_path = filename "
            "WHERE filename IS NOT NULL AND filename != ''"
        )

    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('filename')
