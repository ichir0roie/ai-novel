"""location に参考地域・参考文化・参考時代を追加

Revision ID: 8f1c2e4b9a3d
Revises: 4da2f1f9d845
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1c2e4b9a3d'
down_revision: Union[str, Sequence[str], None] = '4da2f1f9d845'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sample_region', sa.String(), nullable=True, comment='参考にした実在の地域(例: 「北欧」「地中海沿岸」)。固有名詞をそのまま使うのではなく、地理・気候・景観の手がかりとして持つ'))
        batch_op.add_column(sa.Column('sample_culture', sa.String(), nullable=True, comment='参考にした実在の文化(例: 「遊牧」「稲作」)。風習・生活様式・価値観の手がかりとして持つ'))
        batch_op.add_column(sa.Column('sample_era', sa.String(), nullable=True, comment='参考にした実在の時代(例: 「中世」「産業革命期」)。技術水準・社会制度の手がかりとして持つ'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('location', schema=None) as batch_op:
        batch_op.drop_column('sample_era')
        batch_op.drop_column('sample_culture')
        batch_op.drop_column('sample_region')
