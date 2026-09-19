"""id を実主キーに、filepath は unique 列へ

Revision ID: 6a507ffc8bdb
Revises: 04072625802a
Create Date: 2026-09-19 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from DEM.db.schema import Base


# revision identifiers, used by Alembic.
revision: str = '6a507ffc8bdb'
down_revision: Union[str, Sequence[str], None] = '04072625802a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# filepath が実質の主キーだった MarkdownBase 系のテーブル。
# 2 段階マイグレーション（stage1: id 列追加、stage2: FK を id へ）を終えた今、
# ここで id を本当の PRIMARY KEY にし、filepath はただの UNIQUE 列に落とす。
# 列構成そのものは stage1/2 の時点で schema.py の定義と一致しているので、
# 列ごとの ALTER ではなく「schema.py の Table 定義でそのまま作り直す」。
_MARKDOWN_TABLES = (
    "character", "character_drive", "episode", "event",
    "kind", "location", "object", "skill", "story", "term",
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

    # SQLite の ALTER TABLE RENAME は、他テーブルの FK 参照テキストを
    # リネーム先の名前へ自動的に書き換える。そのため「1 テーブルずつ
    # rename → create → copy → drop」を回すと、まだ処理していない
    # テーブルを later rename したときに、既に作り直した側の FK が
    # 存在しない "_old_<table>" を指したまま壊れてしまう。
    # これを避けるため、全テーブルの rename を先に終わらせてから
    # まとめて create し直す（rename が全部終わったあとは、どの
    # テーブルも re-create の対象にならないので巻き込まれない）。

    # 1) 退避
    for table in _MARKDOWN_TABLES:
        op.rename_table(table, f"_old_{table}")
        _drop_stale_indexes(bind, f"_old_{table}")

    # 2) schema.py の最終形で作り直す
    for table in _MARKDOWN_TABLES:
        Base.metadata.tables[table].create(bind=bind)

    # 3) データをコピー
    for table in _MARKDOWN_TABLES:
        columns = [c.name for c in Base.metadata.tables[table].columns]
        col_list = ", ".join(f'"{c}"' for c in columns)
        op.execute(
            f'INSERT INTO "{table}" ({col_list}) '
            f'SELECT {col_list} FROM "_old_{table}"'
        )

    # 4) 退避テーブルを削除
    for table in _MARKDOWN_TABLES:
        op.drop_table(f"_old_{table}")


def downgrade() -> None:
    """Downgrade schema.

    filepath を主キーへ戻し、id は普通の NOT NULL 列に落とす。
    列構成自体は変わらないので、PRIMARY KEY を filepath に張り直した
    テーブルを作って、そのままコピーする。
    """
    bind = op.get_bind()
    metadata = sa.MetaData()

    restored_tables = {}
    for table in _MARKDOWN_TABLES:
        current = Base.metadata.tables[table]
        old_columns = []
        for c in current.columns:
            copied = c.copy()
            copied.primary_key = (c.name == "filepath")
            copied.autoincrement = False
            old_columns.append(copied)
        restored_tables[table] = sa.Table(table, metadata, *old_columns)

    # 1) 退避
    for table in _MARKDOWN_TABLES:
        op.rename_table(table, f"_new_{table}")
        _drop_stale_indexes(bind, f"_new_{table}")

    # 2) filepath 主キー版を作り直す
    for table in reversed(_MARKDOWN_TABLES):
        restored_tables[table].create(bind=bind)

    # 3) データをコピー
    for table in _MARKDOWN_TABLES:
        columns = [c.name for c in restored_tables[table].columns]
        col_list = ", ".join(f'"{c}"' for c in columns)
        op.execute(
            f'INSERT INTO "{table}" ({col_list}) '
            f'SELECT {col_list} FROM "_new_{table}"'
        )

    # 4) 退避テーブルを削除
    for table in _MARKDOWN_TABLES:
        op.drop_table(f"_new_{table}")
