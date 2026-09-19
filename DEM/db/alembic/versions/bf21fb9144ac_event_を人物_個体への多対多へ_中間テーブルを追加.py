"""event を人物・個体への多対多へ、中間テーブルを追加

`event.character_id` `event.object_id`（単一の FK）を、`event_character`
`event_object`（中間テーブル）へ置き換える。一つの出来事に何人・何個体でも
掛かれるようにするため。既存の値はそのまま中間テーブルへ一件ずつ移す。

Revision ID: bf21fb9144ac
Revises: bb6ee1915531
Create Date: 2026-09-19 15:28:26.690109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf21fb9144ac'
down_revision: Union[str, Sequence[str], None] = 'bb6ee1915531'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'event_character',
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('character_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['character.id']),
        sa.ForeignKeyConstraint(['event_id'], ['event.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('event_character', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_event_character_character_id'), ['character_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_character_event_id'), ['event_id'], unique=False)

    op.create_table(
        'event_object',
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('object_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['event.id']),
        sa.ForeignKeyConstraint(['object_id'], ['object.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('event_object', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_event_object_event_id'), ['event_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_object_object_id'), ['object_id'], unique=False)

    # 既存の event.character_id / object_id を、中間テーブルへ一件ずつ移す
    op.execute(
        'INSERT INTO event_character (event_id, character_id) '
        'SELECT id, character_id FROM event WHERE character_id IS NOT NULL'
    )
    op.execute(
        'INSERT INTO event_object (event_id, object_id) '
        'SELECT id, object_id FROM event WHERE object_id IS NOT NULL'
    )

    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_event_character_id'))
        batch_op.drop_index(batch_op.f('ix_event_object_id'))
        batch_op.drop_column('character_id')
        batch_op.drop_column('object_id')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('character_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('object_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key('fk_event_character_id_character', 'character', ['character_id'], ['id'])
        batch_op.create_foreign_key('fk_event_object_id_object', 'object', ['object_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_event_character_id'), ['character_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_object_id'), ['object_id'], unique=False)

    # 中間テーブルから一件ずつ戻す。一つの出来事に複数人・複数個体が
    # 掛かっていた場合は、id が一番小さいものだけが残る（この形の宿命で、
    # 多対多を単一の FK へは戻しきれない）
    op.execute(
        'UPDATE event SET character_id = ('
        '  SELECT MIN(character_id) FROM event_character WHERE event_character.event_id = event.id'
        ')'
    )
    op.execute(
        'UPDATE event SET object_id = ('
        '  SELECT MIN(object_id) FROM event_object WHERE event_object.event_id = event.id'
        ')'
    )

    with op.batch_alter_table('event_object', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_event_object_object_id'))
        batch_op.drop_index(batch_op.f('ix_event_object_event_id'))
    op.drop_table('event_object')

    with op.batch_alter_table('event_character', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_event_character_event_id'))
        batch_op.drop_index(batch_op.f('ix_event_character_character_id'))
    op.drop_table('event_character')
