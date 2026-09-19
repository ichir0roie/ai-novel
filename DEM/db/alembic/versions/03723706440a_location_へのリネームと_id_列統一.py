"""location へのリネームと id 列統一

Revision ID: 03723706440a
Revises: 65daf9c2aece
Create Date: 2026-09-19 19:11:30.114886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03723706440a'
down_revision: Union[str, Sequence[str], None] = '65daf9c2aece'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# filepath を主キーに持つ MarkdownBase 系のテーブル。
# 既存データがあるので、まず NULL 許容で id を足し、
# rowid で採番してから NOT NULL に締める（2 段階マイグレーションの 1 段目）。
_MARKDOWN_TABLES = (
    "character", "character_drive", "episode", "event",
    "kind", "location", "object", "skill", "story", "term",
)


def upgrade() -> None:
    """Upgrade schema."""
    for table in _MARKDOWN_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("id", sa.BigInteger(), nullable=True))

        op.execute(f"UPDATE {table} SET id = rowid")

        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column("id", existing_type=sa.BigInteger(), nullable=False)

    # 既存の RecordBase 系テーブルは id 列は既にあるので型を BigInteger に揃えるだけ。
    with op.batch_alter_table('character_place', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=False,
               autoincrement=True)

    with op.batch_alter_table('character_skill', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=False,
               autoincrement=True)

    with op.batch_alter_table('object_place', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=False,
               autoincrement=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('object_place', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=False,
               autoincrement=True)

    with op.batch_alter_table('character_skill', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=False,
               autoincrement=True)

    with op.batch_alter_table('character_place', schema=None) as batch_op:
        batch_op.alter_column('id',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=False,
               autoincrement=True)

    for table in reversed(_MARKDOWN_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("id")
