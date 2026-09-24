"""rename story_summary to episode_summary

Revision ID: e1c9532b3315
Revises: fbab84187d1d
Create Date: 2026-09-24 20:45:53.955574

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e1c9532b3315'
down_revision: Union[str, Sequence[str], None] = 'fbab84187d1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 自動生成は drop_table('story_summary') + create_table('episode_summary') を出すが、
    # それでは既存の行が消える。rename_table + 索引の付け替えで、行(id・データ)をそのまま残す。
    op.rename_table('story_summary', 'episode_summary')
    op.drop_index('ix_story_summary_episode_id', table_name='episode_summary')
    op.drop_index('ix_story_summary_story_id', table_name='episode_summary')
    op.create_index('ix_episode_summary_episode_id', 'episode_summary', ['episode_id'], unique=True)
    op.create_index('ix_episode_summary_story_id', 'episode_summary', ['story_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_episode_summary_episode_id', table_name='episode_summary')
    op.drop_index('ix_episode_summary_story_id', table_name='episode_summary')
    op.create_index('ix_story_summary_episode_id', 'episode_summary', ['episode_id'], unique=True)
    op.create_index('ix_story_summary_story_id', 'episode_summary', ['story_id'], unique=False)
    op.rename_table('episode_summary', 'story_summary')
