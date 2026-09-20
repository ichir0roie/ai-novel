"""技(Skill)システムを廃止する

技は表で管理せず、人物の能力・特徴は `Character.text` に文章として
書き込む方針に変える。`character_skill`(中間表)`skill`(カタログ本体)の
両方と、`Character.skills` リレーションを落とす。

Revision ID: 7e559b4d98d3
Revises: 404d6a1bf8d5
Create Date: 2026-09-20 23:01:47.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e559b4d98d3'
down_revision: Union[str, Sequence[str], None] = '404d6a1bf8d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('character_skill')
    op.drop_table('skill')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        'skill',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('cost', sa.Integer(), nullable=True),
        sa.Column('effect', sa.String(), nullable=False),
        sa.Column('range', sa.String(), nullable=True),
        sa.Column('duration', sa.String(), nullable=True),
        sa.Column('target', sa.String(), nullable=True),
        sa.Column('constraint', sa.String(), nullable=True),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('tag', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'character_skill',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('character_id', sa.Integer(), nullable=True),
        sa.Column('object_id', sa.Integer(), nullable=True),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['character.id']),
        sa.ForeignKeyConstraint(['object_id'], ['object.id']),
        sa.ForeignKeyConstraint(['skill_id'], ['skill.id']),
        sa.PrimaryKeyConstraint('id'),
    )
