"""人物からworld_influenceを外しtextを任意に

Revision ID: 796c5ab097d4
Revises: 7e4ab2f14e6c
Create Date: 2026-09-22 22:43:51.564450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '796c5ab097d4'
down_revision: Union[str, Sequence[str], None] = '7e4ab2f14e6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('character') as batch_op:
        batch_op.alter_column('text', existing_type=sa.String(), nullable=True)
        batch_op.drop_column('world_influence')


def downgrade() -> None:
    """Downgrade schema."""
    # NOT NULL に戻す前に空文字へ寄せないと、text が NULL の行で失敗する。
    op.execute("UPDATE character SET text = '' WHERE text IS NULL")
    with op.batch_alter_table('character') as batch_op:
        batch_op.add_column(sa.Column('world_influence', sa.Integer(), nullable=False, server_default='0'))
        batch_op.alter_column('text', existing_type=sa.String(), nullable=False)
