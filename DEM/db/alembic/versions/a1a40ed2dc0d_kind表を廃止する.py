"""kind表を廃止する

`Kind`(種別のカタログ)は定義が曖昧なため廃止する。`object` `character`
の `kind_id` 列と、`kind` 表そのものを落とす。

Revision ID: a1a40ed2dc0d
Revises: 8f1c2e4b9a3d
Create Date: 2026-09-20 18:06:54.088474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1a40ed2dc0d'
down_revision: Union[str, Sequence[str], None] = '8f1c2e4b9a3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('object', schema=None) as batch_op:
        batch_op.drop_column('kind_id')

    with op.batch_alter_table('character', schema=None) as batch_op:
        batch_op.drop_column('kind_id')

    op.drop_table('kind')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        'kind',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('filepath', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('read', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('character', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kind_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_character_kind_id_kind', 'kind', ['kind_id'], ['id'])

    with op.batch_alter_table('object', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kind_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_object_kind_id_kind', 'kind', ['kind_id'], ['id'])
