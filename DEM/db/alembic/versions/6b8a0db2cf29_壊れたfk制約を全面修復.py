"""壊れたfk制約を全面修復

Revision ID: 6b8a0db2cf29
Revises: 6a507ffc8bdb
Create Date: 2026-09-19 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from DEM.db.schema import Base


# revision identifiers, used by Alembic.
revision: str = '6b8a0db2cf29'
down_revision: Union[str, Sequence[str], None] = '6a507ffc8bdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 過去のマイグレーション(04072625802a, 6a507ffc8bdb)は「1 テーブルずつ
# rename → create → copy → drop」を回していた。だが SQLite の
# ALTER TABLE RENAME は、他テーブルの FK 参照テキストをリネーム先の名前へ
# 自動的に書き換えてしまうため、まだ処理していないテーブルを later rename
# したとき、既に作り直したテーブルの FK が実在しない "_old_<table>" /
# "_alembic_tmp_<table>" を指したまま壊れて残っていた
# (PRAGMA foreign_key_check で実際に検出できる)。
#
# ここでは FK を持つ全テーブルを「全部 rename → 全部 create → 全部 copy →
# 全部 drop」の 4 フェーズでまとめて作り直し、schema.py の定義どおりの
# 正しい FK を張り直す。列構成・データ自体は変える必要がないので、
# 単純にコピーするだけでよい。
_FK_TABLES = (
    "character", "character_drive", "episode", "event",
    "kind", "location", "object", "skill", "story", "term",
    "object_place", "character_place", "character_skill",
)


def _drop_stale_indexes(bind, old_name: str) -> None:
    for (ix_name,) in bind.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND tbl_name=? AND sql IS NOT NULL", (old_name,)
    ).fetchall():
        bind.exec_driver_sql(f'DROP INDEX "{ix_name}"')


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    for table in _FK_TABLES:
        op.rename_table(table, f"_old_{table}")
        _drop_stale_indexes(bind, f"_old_{table}")

    for table in _FK_TABLES:
        Base.metadata.tables[table].create(bind=bind)

    for table in _FK_TABLES:
        columns = [c.name for c in Base.metadata.tables[table].columns]
        col_list = ", ".join(f'"{c}"' for c in columns)
        op.execute(
            f'INSERT INTO "{table}" ({col_list}) '
            f'SELECT {col_list} FROM "_old_{table}"'
        )

    for table in _FK_TABLES:
        op.drop_table(f"_old_{table}")


def downgrade() -> None:
    """Downgrade schema.

    FK の張り方を直しただけで列構成やデータは変えていないため、
    downgrade は no-op でよい(一つ前のリビジョンに戻っても
    データが壊れることはない)。
    """
    pass
