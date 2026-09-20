"""fk列をfilepathからidへ置換

Revision ID: 04072625802a
Revises: 03723706440a
Create Date: 2026-09-19 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04072625802a'
down_revision: Union[str, Sequence[str], None] = '03723706440a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 2 段階マイグレーションの 2 段目。filepath の文字列を格納していた FK 列を、
# 参照先テーブルの id(BigInteger)へ差し替える。
# table -> [(column, referenced_table), ...]
_FK_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "location": [("parent_id", "location")],
    "event": [
        ("parent_event_id", "event"),
        ("place_id", "location"),
        ("character_id", "character"),
        ("object_id", "object"),
    ],
    "object": [
        ("root_place_name", "location"),
        ("kind_id", "kind"),
    ],
    "character": [
        ("root_place_name", "location"),
        ("kind_id", "kind"),
        ("born_place_id", "location"),
        ("belong_id", "object"),
    ],
    "object_place": [
        ("object_id", "object"),
        ("place_id", "location"),
    ],
    "character_place": [
        ("character_id", "character"),
        ("place_id", "location"),
    ],
    "character_skill": [
        ("character_id", "character"),
        ("object_id", "object"),
        ("skill_id", "skill"),
    ],
    "character_drive": [
        ("character_id", "character"),
    ],
    "term": [
        ("restrict_world_id", "location"),
        ("restrict_planet_id", "location"),
        ("restrict_place_id", "location"),
        ("parent_term_id", "term"),
    ],
    "story": [
        ("world_id", "location"),
        ("place_id", "location"),
    ],
    "episode": [
        ("story_id", "story"),
    ],
}

# 元の型に戻すときのため(downgrade)。全て String(filepath)。
_ORIGINAL_TYPE = sa.String()


def _tmp(column: str) -> str:
    return f"{column}__tmp_id"


def upgrade() -> None:
    """Upgrade schema."""
    # 1) 一時列(BigInteger)を追加
    for table, columns in _FK_COLUMNS.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column, _ in columns:
                batch_op.add_column(sa.Column(_tmp(column), sa.BigInteger(), nullable=True))

    # 2) filepath を辿って id を埋める(自己参照テーブルも filepath 列自体は
    #    まだ残っているので、この時点なら参照できる)
    for table, columns in _FK_COLUMNS.items():
        for column, ref_table in columns:
            op.execute(
                f'UPDATE "{table}" SET "{_tmp(column)}" = ('
                f'  SELECT r.id FROM "{ref_table}" r WHERE r.filepath = "{table}"."{column}"'
                f')'
                f'WHERE "{table}"."{column}" IS NOT NULL'
            )

    # 3) 旧列を落として一時列を本来の名前へ戻し、FK 制約を張り直す。
    #    drop/rename/create_foreign_key を同じ batch 内でまとめて行う
    #    (batch を分けると、リネーム後の列に対する既存インデックスの
    #    複製で名前が衝突する)。
    #    旧列に張られていたインデックスは、リネーム後の同名インデックス複製と
    #    衝突するので先に落としておく。
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, columns in _FK_COLUMNS.items():
        target_columns = {column for column, _ in columns}
        stale_indexes = [
            (ix["name"], ix["column_names"]) for ix in inspector.get_indexes(table)
            if set(ix["column_names"]) & target_columns
        ]
        with op.batch_alter_table(table, schema=None) as batch_op:
            for ix_name, _ in stale_indexes:
                batch_op.drop_index(ix_name)
            for column, ref_table in columns:
                batch_op.drop_column(column)
            for column, ref_table in columns:
                batch_op.alter_column(
                    _tmp(column), new_column_name=column,
                    existing_type=sa.BigInteger(),
                )
            for column, ref_table in columns:
                batch_op.create_foreign_key(
                    f"fk_{table}_{column}_{ref_table}",
                    ref_table, [column], ["id"],
                )
        # batch の外で張り直す(batch 内で drop/create を両方行うと、
        # 内部の新旧テーブル間インデックス複製処理が壊れる)
        for ix_name, ix_columns in stale_indexes:
            op.create_index(ix_name, table, ix_columns)


def downgrade() -> None:
    """Downgrade schema."""
    # id -> filepath へ戻す。id 列自体は消さず、値だけ filepath 文字列に戻す。
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, columns in reversed(list(_FK_COLUMNS.items())):
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column, _ in columns:
                batch_op.add_column(sa.Column(_tmp(column), sa.String(), nullable=True))

        for column, ref_table in columns:
            op.execute(
                f'UPDATE "{table}" SET "{_tmp(column)}" = ('
                f'  SELECT r.filepath FROM "{ref_table}" r WHERE r.id = "{table}"."{column}"'
                f')'
                f'WHERE "{table}"."{column}" IS NOT NULL'
            )

        target_columns = {column for column, _ in columns}
        stale_indexes = [
            (ix["name"], ix["column_names"]) for ix in inspector.get_indexes(table)
            if set(ix["column_names"]) & target_columns
        ]
        with op.batch_alter_table(table, schema=None) as batch_op:
            for ix_name, _ in stale_indexes:
                batch_op.drop_index(ix_name)
            for column, _ in columns:
                batch_op.drop_column(column)
            for column, _ in columns:
                batch_op.alter_column(
                    _tmp(column), new_column_name=column,
                    existing_type=sa.String(),
                )
        for ix_name, ix_columns in stale_indexes:
            op.create_index(ix_name, table, ix_columns)
