"""アイデアの場所をlocation_idにしstart_endと自動生成フラグを足す

Revision ID: 51a2863be722
Revises: 37f8b0a380e9
Create Date: 2026-09-24 22:19:37.432324

三つの restrict_* のうち、いちばん狭い場所(place → planet → world の順)を location_id へ移す。
種別「候補」の行は auto_generated を立てる(種別はあとで直す)。

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51a2863be722'
down_revision: Union[str, Sequence[str], None] = '37f8b0a380e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auto_generated', sa.Boolean(), nullable=False, server_default=sa.false(), comment='本文から自動で足した未確認のアイデアか。検索・生成には他と同じく出る。確かめたら false にする'))
        batch_op.add_column(sa.Column('location_id', sa.Integer(), nullable=True, comment='効く場所。この場所とその配下で効く。空ならどこにも効かない'))
        batch_op.add_column(sa.Column('start', sa.BigInteger(), nullable=True, comment='効き始める時刻。出来事の時刻と比べる。空なら始まりを限らない'))
        batch_op.add_column(sa.Column('end', sa.BigInteger(), nullable=True, comment='効き終わる時刻(この時刻からは効かない)。空なら終わりを限らない'))

    op.execute("UPDATE idea SET location_id = COALESCE(restrict_place_id, restrict_planet_id, restrict_world_id)")
    op.execute("UPDATE idea SET auto_generated = 1 WHERE kind = '候補'")

    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.alter_column('auto_generated', server_default=None)
        batch_op.create_index(batch_op.f('ix_idea_location_id'), ['location_id'], unique=False)
        batch_op.create_foreign_key('fk_idea_location_id_location', 'location', ['location_id'], ['id'])
        batch_op.drop_column('restrict_planet_id')
        batch_op.drop_column('restrict_place_id')
        batch_op.drop_column('restrict_world_id')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.add_column(sa.Column('restrict_world_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('restrict_place_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('restrict_planet_id', sa.INTEGER(), nullable=True))

    # 三つのどれに当たっても同じく効いていたので、どの段の場所かは見ずに restrict_place_id へ戻す
    op.execute("UPDATE idea SET restrict_place_id = location_id")
    op.execute("UPDATE idea SET kind = '候補' WHERE auto_generated = 1")

    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.drop_constraint('fk_idea_location_id_location', type_='foreignkey')
        batch_op.create_foreign_key('fk_idea_restrict_world_id_location', 'location', ['restrict_world_id'], ['id'])
        batch_op.create_foreign_key('fk_idea_restrict_planet_id_location', 'location', ['restrict_planet_id'], ['id'])
        batch_op.create_foreign_key('fk_idea_restrict_place_id_location', 'location', ['restrict_place_id'], ['id'])
        batch_op.drop_index(batch_op.f('ix_idea_location_id'))
        batch_op.drop_column('end')
        batch_op.drop_column('start')
        batch_op.drop_column('location_id')
        batch_op.drop_column('auto_generated')
