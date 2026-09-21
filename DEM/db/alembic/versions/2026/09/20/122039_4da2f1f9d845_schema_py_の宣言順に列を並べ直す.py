"""schema.py の宣言順に列を並べ直す

過去のマイグレーション(`filepath`→`id` の置換、`id` を実主キーに直す、
`location` への広さ・環境の追加など)は SQLite の `ALTER TABLE ADD COLUMN`
で列を末尾に足してきたため、db 上の物理的な列順が `DEM/db/schema.py` の
宣言順とずれてしまっていた(例: `location` は `area` `environment` が
末尾に付いた状態、`id` `filepath` の前後が逆、等)。DBeaver で見たときの
列順はこの物理順そのままなので見にくい。

SQLite は列の並べ替えを直接サポートしないため、`batch_alter_table` の
`copy_from`(ORM モデルの `__table__` = `schema.py` の宣言順そのもの)を
使い、対象の表を丸ごと作り直して列順を揃える(データ・index・制約は
`batch_alter_table` がそのまま引き継ぐ)。

Revision ID: 4da2f1f9d845
Revises: 4d305c506a4c
Create Date: 2026-09-20 12:20:39.841402

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from DEM.db.schema import (
    Character, Episode, Event, Location, Object, StampType,
    Story, Term,
)

# revision identifiers, used by Alembic.
revision: str = '4da2f1f9d845'
down_revision: Union[str, Sequence[str], None] = '4d305c506a4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `Skill` はこの後のマイグレーション(技システムの廃止)で表ごと落ちたため、
# 当時の列順を静的な Table として書き残す(モデルクラスは既に無い)。
_skill_table_at_this_point = sa.Table(
    "skill", sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("name", sa.String),
    sa.Column("cost", sa.Integer, default=1),
    sa.Column("effect", sa.String, nullable=False),
    sa.Column("range", sa.String),
    sa.Column("duration", sa.String),
    sa.Column("target", sa.String),
    sa.Column("constraint", sa.String),
    sa.Column("text", sa.String, nullable=False),
    sa.Column("tag", sa.String, nullable=True),
)

# `CharacterDrive` はのちに character_plot への一本化で表ごと落ちたため、
# 当時の列順を静的な Table として書き残す(モデルクラスは既に無い)。
_character_drive_table_at_this_point = sa.Table(
    "character_drive", sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("character_id", sa.Integer, sa.ForeignKey("character.id")),
    sa.Column("text", sa.String, nullable=False),
    sa.Column("level", sa.Integer, default=1, nullable=False),
    sa.Column("start", StampType),
    sa.Column("end", StampType),
    sa.Column("filepath", sa.String, nullable=True),
)

# 実際に物理列順がずれていた表だけを対象にする
# (`DEM/db/schema.py` の宣言順と一致している表は触らない)。
# `kind` 表はこの後のマイグレーションで削除されるため、ここでは対象から外す。
_REORDERED_TABLES = (
    _skill_table_at_this_point, Character.__table__, _character_drive_table_at_this_point,
    Episode.__table__, Location.__table__, Object.__table__,
    Story.__table__, Term.__table__, Event.__table__,
)


def upgrade() -> None:
    """`schema.py` の宣言順に、対象の表を作り直す(データはそのまま引き継ぐ)。"""
    for table in _REORDERED_TABLES:
        with op.batch_alter_table(
            table.name, copy_from=table, recreate="always",
        ):
            pass


def downgrade() -> None:
    """列順だけの変更なので、意図的に downgrade はしない(データに影響しない)。"""
