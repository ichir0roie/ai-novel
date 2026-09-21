"""tag列をdirectory_path列に置き換える

Revision ID: ce022c39f4f4
Revises: bc7493a69e2c
Create Date: 2026-09-21 11:55:58.815965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce022c39f4f4'
down_revision: Union[str, Sequence[str], None] = 'bc7493a69e2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    'character', 'character_drive', 'episode', 'event', 'location',
    'location_resource', 'object', 'plot', 'story', 'term',
)

NEW_COMMENT = (
    'import,export時の配置先。worlds/{table}/ からの相対ディレクトリパス。'
    '空ならテーブル直下に置く'
)
OLD_COMMENT = 'import,export時のファイル名用'


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                'tag', new_column_name='directory_path', existing_type=sa.String(),
                existing_nullable=True, existing_comment=OLD_COMMENT, comment=NEW_COMMENT)


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                'directory_path', new_column_name='tag', existing_type=sa.String(),
                existing_nullable=True, existing_comment=NEW_COMMENT, comment=OLD_COMMENT)
