"""rename term to idea

Revision ID: 167e2faa3717
Revises: 56c6bd7ffe26
Create Date: 2026-09-24 19:56:31.905056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '167e2faa3717'
down_revision: Union[str, Sequence[str], None] = '56c6bd7ffe26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 自動生成は drop_table('term') + create_table('idea') を出すが、それでは既存の行が
    # 消える。rename_table + 列名の付け替えで、行(id・データ)をそのまま残す。
    op.rename_table('term', 'idea')
    with op.batch_alter_table('idea') as batch_op:
        batch_op.alter_column(
            'parent_term_id', new_column_name='parent_idea_id',
            existing_type=sa.Integer(),
            existing_comment='上位の語。置いたディレクトリで決まる',
            comment='上位のアイデア。置いたディレクトリで決まる')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('idea') as batch_op:
        batch_op.alter_column(
            'parent_idea_id', new_column_name='parent_term_id',
            existing_type=sa.Integer(),
            existing_comment='上位のアイデア。置いたディレクトリで決まる',
            comment='上位の語。置いたディレクトリで決まる')
    op.rename_table('idea', 'term')
