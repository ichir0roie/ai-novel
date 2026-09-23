"""character テーブルのマイグレーション。

- 7e4ab2f14e6c: 性格を整数から五段階へ
- 796c5ab097d4: world_influence を外し、text を任意に
- 5546b82c7972: character_relation を足す
- c3a1f0d2b4e6: location に polygon を足す
- bacc670e4a5f: character_relation に start/end を足す
- e849a5b683f6: character の read を外す
- 5d316428a6aa: character に sub_character を足す
"""
import sqlite3

import pytest
from alembic import command
from alembic.config import Config

from DEM.db.schema import PERSONALITY_COLUMNS, Base, engine
from DEM.tool.test import TEST_DB_PATH

HEAD_REVISION = "5d316428a6aa"


@pytest.fixture
def old_style_db():
    """性格列を旧来の INTEGER、text を NOT NULL に戻し、read と world_influence を持つ人物を並べた db。

    あとのリビジョンで足す character_relation と location.polygon も無い形にする。
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(TEST_DB_PATH)
    # ALTER TABLE ADD COLUMN の NOT NULL は既定値を強いられ、それが upgrade 後も残る。
    # 旧 db と同じ既定値無しの列にするため、CREATE 文を書き換えて張り直す。
    create_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'character'").fetchone()[0]
    for column in PERSONALITY_COLUMNS:
        create_sql = create_sql.replace(f"\t{column} VARCHAR NOT NULL", f"\t{column} INTEGER NOT NULL DEFAULT 0")
    create_sql = (create_sql
                  .replace("\ttext VARCHAR, ", "\ttext VARCHAR NOT NULL, ")
                  .replace("\tname VARCHAR, ", "\tname VARCHAR, \n\tread VARCHAR, \n\tworld_influence INTEGER NOT NULL, ")
                  .replace("\n\tsub_character BOOLEAN NOT NULL, ", ""))
    assert "world_influence" in create_sql and "text VARCHAR NOT NULL" in create_sql
    assert "sub_character" not in create_sql
    conn.execute("DROP TABLE character")
    conn.execute(create_sql)
    conn.execute("DROP TABLE character_relation")
    location_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'location'").fetchone()[0]
    assert "\tpolygon JSON, " in location_sql
    conn.execute("DROP TABLE location")
    conn.execute(location_sql.replace("\tpolygon JSON, ", ""))
    values = [-5, -4, -3, -1, 0, 1, 3, 4, 5]
    for value in values:
        conn.execute(
            'INSERT INTO character (name, text, kind, world_influence, sincerity) '
            "VALUES (?, '', '人物', 3, ?)", (f"v{value}", value))
    conn.commit()
    conn.close()
    yield values


def _config() -> Config:
    return Config("DEM/db/alembic/alembic.ini")


def _columns(conn, table="character") -> dict[str, tuple[str, int, str | None]]:
    """列名 -> (型, notnull, 既定値)"""
    return {row[1]: (row[2], row[3], row[4]) for row in conn.execute(f"PRAGMA table_info({table})")}


def test_upgrade_maps_integers_to_levels(old_style_db):
    command.upgrade(_config(), "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == (HEAD_REVISION,)
    columns = _columns(conn)
    for column in PERSONALITY_COLUMNS:
        assert columns[column] == ("VARCHAR", 1, "'並'"), column
    rows = dict(conn.execute("SELECT name, sincerity FROM character").fetchall())
    assert rows == {
        "v-5": "無", "v-4": "無", "v-3": "低", "v-1": "低", "v0": "並",
        "v1": "高", "v3": "高", "v4": "必", "v5": "必",
    }
    # 触っていない軸は既定の 0 → 並
    assert set(r[0] for r in conn.execute("SELECT imagination FROM character")) == {"並"}
    conn.close()


def test_upgrade_drops_world_influence_and_allows_null_text(old_style_db):
    command.upgrade(_config(), "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    columns = _columns(conn)
    assert "world_influence" not in columns
    assert "read" not in columns
    assert columns["text"][1] == 0
    conn.execute("INSERT INTO character (name, kind) VALUES ('無説明', '人物')")
    assert conn.execute("SELECT text FROM character WHERE name = '無説明'").fetchone() == (None,)
    conn.close()


def test_upgrade_adds_location_polygon(old_style_db):
    command.upgrade(_config(), "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    assert _columns(conn, "location")["polygon"] == ("JSON", 0, None)
    conn.execute("INSERT INTO location (name, kind, text, active_random_generation) VALUES ('輪郭なし', '国', '', 0)")
    assert conn.execute("SELECT polygon FROM location WHERE name = '輪郭なし'").fetchone() == (None,)
    conn.close()


def test_downgrade_drops_location_polygon(old_style_db):
    cfg = _config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "5546b82c7972")

    conn = sqlite3.connect(TEST_DB_PATH)
    assert "polygon" not in _columns(conn, "location")
    conn.close()


def test_downgrade_restores_integers(old_style_db):
    cfg = _config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    conn = sqlite3.connect(TEST_DB_PATH)
    columns = _columns(conn)
    for column in PERSONALITY_COLUMNS:
        assert columns[column][0] == "INTEGER", column
    rows = dict(conn.execute("SELECT name, sincerity FROM character").fetchall())
    assert rows == {
        "v-5": -5, "v-4": -5, "v-3": -2, "v-1": -2, "v0": 0,
        "v1": 2, "v3": 2, "v4": 5, "v5": 5,
    }
    conn.close()


def test_downgrade_restores_world_influence_and_not_null_text(old_style_db):
    cfg = _config()
    command.upgrade(cfg, "head")
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.execute("INSERT INTO character (name, kind) VALUES ('無説明', '人物')")
    conn.commit()
    conn.close()
    command.downgrade(cfg, "7e4ab2f14e6c")

    conn = sqlite3.connect(TEST_DB_PATH)
    columns = _columns(conn)
    assert columns["world_influence"][1:] == (1, "'0'")
    assert columns["text"][1] == 1
    # 落とした値は戻らず既定の 0、NULL だった text は空文字になる
    assert set(r[0] for r in conn.execute("SELECT world_influence FROM character")) == {0}
    assert conn.execute("SELECT text FROM character WHERE name = '無説明'").fetchone() == ("",)
    conn.close()


def test_migrated_db_matches_schema(old_style_db):
    """upgrade 後の db と schema.py に差分が無い(`alembic check` と同じ)。"""
    cfg = _config()
    command.upgrade(cfg, "head")
    command.check(cfg)
