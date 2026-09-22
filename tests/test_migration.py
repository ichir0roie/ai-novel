"""性格を整数から五段階へ移すマイグレーション(7e4ab2f14e6c)。"""
import sqlite3

import pytest
from alembic import command
from alembic.config import Config

from DEM.db.schema import PERSONALITY_COLUMNS, Base, engine
from DEM.tool.test import TEST_DB_PATH

REVISION = "7e4ab2f14e6c"


@pytest.fixture
def old_style_db():
    """性格列を旧来の INTEGER に戻し、-5〜5 の値を持つ人物を並べた db。"""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(TEST_DB_PATH)
    for column in PERSONALITY_COLUMNS:
        conn.execute(f'ALTER TABLE character DROP COLUMN "{column}"')
        conn.execute(f'ALTER TABLE character ADD COLUMN "{column}" INTEGER NOT NULL DEFAULT 0')
    values = [-5, -4, -3, -1, 0, 1, 3, 4, 5]
    for value in values:
        conn.execute(
            'INSERT INTO character (name, text, kind, world_influence, sincerity) '
            "VALUES (?, '', '人物', 0, ?)", (f"v{value}", value))
    conn.commit()
    conn.close()
    yield values


def _config() -> Config:
    return Config("DEM/db/alembic/alembic.ini")


def _column_types(conn) -> dict[str, tuple[str, str | None]]:
    return {row[1]: (row[2], row[4]) for row in conn.execute("PRAGMA table_info(character)")}


def test_upgrade_maps_integers_to_levels(old_style_db):
    command.upgrade(_config(), "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == (REVISION,)
    types = _column_types(conn)
    for column in PERSONALITY_COLUMNS:
        assert types[column] == ("VARCHAR", "'並'"), column
    rows = dict(conn.execute("SELECT name, sincerity FROM character").fetchall())
    assert rows == {
        "v-5": "無", "v-4": "無", "v-3": "低", "v-1": "低", "v0": "並",
        "v1": "高", "v3": "高", "v4": "必", "v5": "必",
    }
    # 触っていない軸は既定の 0 → 並
    assert set(r[0] for r in conn.execute("SELECT imagination FROM character")) == {"並"}
    conn.close()


def test_downgrade_restores_integers(old_style_db):
    cfg = _config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    conn = sqlite3.connect(TEST_DB_PATH)
    types = _column_types(conn)
    for column in PERSONALITY_COLUMNS:
        assert types[column][0] == "INTEGER", column
    rows = dict(conn.execute("SELECT name, sincerity FROM character").fetchall())
    assert rows == {
        "v-5": -5, "v-4": -5, "v-3": -2, "v-1": -2, "v0": 0,
        "v1": 2, "v3": 2, "v4": 5, "v5": 5,
    }
    conn.close()


def test_migrated_db_matches_schema(old_style_db):
    """upgrade 後の db と schema.py に差分が無い(`alembic check` と同じ)。"""
    cfg = _config()
    command.upgrade(cfg, "head")
    command.check(cfg)
