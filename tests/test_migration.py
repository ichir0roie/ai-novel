"""character テーブルのマイグレーション。

- 7e4ab2f14e6c: 性格を整数から五段階へ
- 796c5ab097d4: world_influence を外し、text を任意に
- 5546b82c7972: character_relation を足す
- c3a1f0d2b4e6: location に polygon を足す
- bacc670e4a5f: character_relation に start/end を足す
- e849a5b683f6: character の read を外す
- 5d316428a6aa: character に sub_character を足す
- 5c15aeb8dd47: plot / character_plot を畳んで落とす
"""
import sqlite3

import pytest
from alembic import command
from alembic.config import Config

from DEM.db.schema import PERSONALITY_COLUMNS, Base, engine
from DEM.db.stamp import Stamp
from DEM.tool.test import TEST_DB_PATH

HEAD_REVISION = "5c15aeb8dd47"

# 5c15aeb8dd47 で落とすまで db にあった、筋書きの二つのテーブル。
_PLOT_TABLE_SQL = (
    'DROP TABLE IF EXISTS plot',
    'DROP TABLE IF EXISTS character_plot',
    'CREATE TABLE plot ('
    ' start BIGINT, "end" BIGINT, id INTEGER NOT NULL, location_id INTEGER,'
    ' text VARCHAR NOT NULL, directory_path VARCHAR, filename VARCHAR,'
    ' PRIMARY KEY (id), FOREIGN KEY(location_id) REFERENCES location (id))',
    'CREATE INDEX ix_plot_location_id ON plot (location_id)',
    'CREATE TABLE character_plot ('
    ' start BIGINT, "end" BIGINT, id INTEGER NOT NULL, character_id INTEGER NOT NULL,'
    ' text VARCHAR NOT NULL, directory_path VARCHAR, filename VARCHAR,'
    ' PRIMARY KEY (id), FOREIGN KEY(character_id) REFERENCES "character" (id))',
    'CREATE INDEX ix_character_plot_character_id ON character_plot (character_id)',
)


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
    # plot / character_plot は schema.py から消えたので、旧 db の形を手で張り直す
    for sql in _PLOT_TABLE_SQL:
        conn.execute(sql)
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


def _seed_plots(values):
    """`old_style_db` を張ったあとの db に、畳む前の筋書きを入れる。"""
    conn = sqlite3.connect(TEST_DB_PATH)
    character_id = conn.execute(
        "SELECT id FROM character WHERE name = ?", (f"v{values[0]}",)).fetchone()[0]
    conn.execute(
        "INSERT INTO character_plot (character_id, start, end, filename, text) "
        "VALUES (?, ?, ?, '誕生', '生まれる')", (character_id, Stamp(1572).to_int(), Stamp(1576).to_int()))
    conn.execute(
        "INSERT INTO character_plot (character_id, start, end, filename, text) "
        "VALUES (?, ?, ?, NULL, '育つ')", (character_id, Stamp(1576).to_int(), None))
    conn.execute("INSERT INTO location (name, kind, text, active_random_generation) "
                 "VALUES ('ノウル', '星', '', 0)")
    location_id = conn.execute("SELECT id FROM location WHERE name = 'ノウル'").fetchone()[0]
    conn.execute("INSERT INTO plot (location_id, start, end, filename, text) "
                 "VALUES (?, ?, NULL, '遥かなる幻想郷まで', '二代の物語')",
                 (location_id, Stamp(1550).to_int()))
    conn.execute("INSERT INTO plot (location_id, start, end, filename, text) "
                 "VALUES (NULL, NULL, NULL, '世界の真実', '裏の筋書き')")
    conn.execute("INSERT INTO story (name, world_id, place_id, narration, state, text) "
                 "VALUES ('遥かなる幻想郷まで', NULL, ?, '三人称', '構想中', '既にある本文')",
                 (location_id,))
    conn.commit()
    conn.close()
    return character_id, location_id


def test_upgrade_folds_character_plots_into_character_text(old_style_db):
    character_id, _ = _seed_plots(old_style_db)

    command.upgrade(_config(), "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    text = conn.execute("SELECT text FROM character WHERE id = ?", (character_id,)).fetchone()[0]
    assert "# plot" in text
    assert "## 1572〜1576 誕生\n生まれる" in text
    assert "## 1576〜\n育つ" in text
    assert "character_plot" not in {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()


def test_upgrade_folds_plots_into_story_text(old_style_db):
    _, location_id = _seed_plots(old_style_db)

    command.upgrade(_config(), "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    # 同じ名前の作品があるものは、その作品の text の末尾へ足す
    existing = conn.execute(
        "SELECT text FROM story WHERE name = '遥かなる幻想郷まで'").fetchone()[0]
    assert existing.startswith("既にある本文")
    assert "# plot\n\n## 1550〜 遥かなる幻想郷まで\n二代の物語" in existing

    # 無いものは作品として新しく立てる
    row = conn.execute(
        "SELECT place_id, world_id, state, text FROM story WHERE name = '世界の真実'").fetchone()
    assert row[0] is None and row[1] is None and row[2] == "構想中"
    assert row[3] == "# plot\n\n## 世界の真実\n裏の筋書き"

    assert "plot" not in {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
