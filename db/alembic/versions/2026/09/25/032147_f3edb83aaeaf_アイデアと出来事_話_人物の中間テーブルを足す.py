"""アイデアと出来事・話・人物の中間テーブルを足す

Revision ID: f3edb83aaeaf
Revises: 7c1f74484959
Create Date: 2026-09-24 18:21:47.551542

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3edb83aaeaf'
down_revision: Union[str, Sequence[str], None] = '7c1f74484959'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """本文が踏まえたアイデアを、出来事・話・人物ごとに持つ中間テーブルを足す。md には出さない。"""
    op.create_table('character_idea',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.Column('idea_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['character.id'], ),
    sa.ForeignKeyConstraint(['idea_id'], ['idea.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('character_id', 'idea_id')
    )
    with op.batch_alter_table('character_idea', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_character_idea_character_id'), ['character_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_character_idea_idea_id'), ['idea_id'], unique=False)

    op.create_table('event_idea',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('idea_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['event.id'], ),
    sa.ForeignKeyConstraint(['idea_id'], ['idea.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id', 'idea_id')
    )
    with op.batch_alter_table('event_idea', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_event_idea_event_id'), ['event_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_idea_idea_id'), ['idea_id'], unique=False)

    op.create_table('episode_idea',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('episode_id', sa.Integer(), nullable=False),
    sa.Column('idea_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['episode_id'], ['episode.id'], ),
    sa.ForeignKeyConstraint(['idea_id'], ['idea.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('episode_id', 'idea_id')
    )
    with op.batch_alter_table('episode_idea', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_episode_idea_episode_id'), ['episode_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_episode_idea_idea_id'), ['idea_id'], unique=False)



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('episode_idea', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_episode_idea_idea_id'))
        batch_op.drop_index(batch_op.f('ix_episode_idea_episode_id'))

    op.drop_table('episode_idea')
    with op.batch_alter_table('event_idea', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_event_idea_idea_id'))
        batch_op.drop_index(batch_op.f('ix_event_idea_event_id'))

    op.drop_table('event_idea')
    with op.batch_alter_table('character_idea', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_character_idea_idea_id'))
        batch_op.drop_index(batch_op.f('ix_character_idea_character_id'))

    op.drop_table('character_idea')
