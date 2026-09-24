"""character テーブルのマイグレーション。

- 7e4ab2f14e6c: 性格を整数から五段階へ
- 796c5ab097d4: world_influence を外し、text を任意に
- 5546b82c7972: character_relation を足す
- c3a1f0d2b4e6: location に polygon を足す
- bacc670e4a5f: character_relation に start/end を足す
- e849a5b683f6: character の read を外す
- 5d316428a6aa: character に sub_character を足す
- 5c15aeb8dd47: plot / character_plot を畳んで落とす
- 052069310f38: 話に start/end・視点・場所・キーテキストを足す
- 24327ee59e1c: event_summary / story_summary を足す
- 82c20d8db0c5: sub_character を反転して main_character へ移す
- cd51e8d34592: event_seed_source / event_seed を足す
- 76fbe5ec1c2e: event_seed_source を元テーブルごとの id 列にする
- f8eefc75dad5: event_seed_source を落とし、元の表の event_seeded で管理する
"""
import sqlite3

import pytest
from alembic import command
from alembic.config import Config

from DEM.db.schema import PERSONALITY_COLUMNS, Base, engine
from DEM.db.stamp import Stamp
from DEM.tool.test import TEST_DB_PATH

HEAD_REVISION = "f8eefc75dad5"

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


_EVENT_SEEDED = "\n\tevent_seeded BOOLEAN NOT NULL, "


@pytest.fixture
def old_style_db():
    """性格列を旧来の INTEGER、text を NOT NULL に戻し、read と world_influence を持つ人物を並べた db。

    あとのリビジョンで足す character_relation・location.polygon・話の
    start/end/viewpoint/place/key・要約の二つのテーブル・出来事の種と event_seeded も無い形にする。
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
                  .replace("\n\tmain_character BOOLEAN NOT NULL, ", "")
                  .replace(_EVENT_SEEDED, ""))
    assert "world_influence" in create_sql and "text VARCHAR NOT NULL" in create_sql
    assert "main_character" not in create_sql
    conn.execute("DROP TABLE character")
    conn.execute(create_sql)
    conn.execute("DROP TABLE character_relation")
    conn.execute("DROP TABLE event_summary")
    conn.execute("DROP TABLE story_summary")
    conn.execute("DROP TABLE event_seed")
    # schema.py から消えたので drop_all では落ちない。前のテストの downgrade が残したものを消す
    conn.execute("DROP TABLE IF EXISTS event_seed_source")
    for table in ("story", "event"):
        conn.execute(f'ALTER TABLE "{table}" DROP COLUMN event_seeded')
    location_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'location'").fetchone()[0]
    assert "\tpolygon JSON, " in location_sql
    conn.execute("DROP TABLE location")
    conn.execute(location_sql.replace("\tpolygon JSON, ", ""))
    episode_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'episode'").fetchone()[0]
    for column in ('start BIGINT', '"end" BIGINT', 'viewpoint VARCHAR', 'place VARCHAR',
                   '"key" VARCHAR DEFAULT \'\' NOT NULL'):
        assert f"\t{column}, " in episode_sql, column
        episode_sql = episode_sql.replace(f"\n\t{column}, ", "")
    conn.execute("DROP TABLE episode")
    conn.execute(episode_sql.replace(_EVENT_SEEDED, ""))
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


def _seed_episode_skeleton():
    """骨組みだけの話を、列を足す前の形(`text` に三行と節が入った形)で入れる。"""
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.execute("INSERT INTO location (name, kind, text, active_random_generation) "
                 "VALUES ('ノウル', '星', '', 0)")
    conn.execute("INSERT INTO story (name, narration, state, text) "
                 "VALUES ('遥かなる幻想郷まで', '三人称', '構想中', '')")
    story_id = conn.execute("SELECT id FROM story").fetchone()[0]
    skeleton = ("- 時期: 1586年 春\n"
                "- 場所: ヴァレンツァ 外れの川\n"
                "- 視点: ノア(十四歳)\n"
                "\n"
                "## 出来事\n\n川へ飛び込む。\n\n## 狙い\n\n力の持て余しを見せる。")
    conn.execute("INSERT INTO episode (story_id, number, title, text, letters, synced) "
                 "VALUES (?, 1, '十四の春', ?, ?, 0)", (story_id, skeleton, len(skeleton)))
    conn.commit()
    conn.close()


def test_upgrade_splits_episode_skeleton_into_columns(old_style_db):
    _seed_episode_skeleton()

    command.upgrade(_config(), "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    start, viewpoint, place, key, text, letters = conn.execute(
        "SELECT start, viewpoint, place, key, text, letters FROM episode").fetchone()
    # 「1586年 春」は台帳の五桁の年と、春=3月へ寄せる
    assert Stamp.from_int(start) == Stamp(11586, 3, 1)
    assert viewpoint == "ノア(十四歳)"
    assert place == "ヴァレンツァ 外れの川"
    assert key.startswith("## 出来事") and "## 狙い" in key
    # 骨組みは種なので、本文は空のまま残す
    assert (text, letters) == ("", 0)
    conn.close()


def test_downgrade_puts_episode_key_back_into_text(old_style_db):
    _seed_episode_skeleton()
    cfg = _config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "5c15aeb8dd47")

    conn = sqlite3.connect(TEST_DB_PATH)
    assert "key" not in _columns(conn, "episode")
    text = conn.execute("SELECT text FROM episode").fetchone()[0]
    assert text.startswith("- 時期: 1586年\n- 場所: ヴァレンツァ 外れの川\n- 視点: ノア(十四歳)")
    assert "## 出来事" in text
    conn.close()


def test_upgrade_adds_summary_tables_and_downgrade_drops_them(old_style_db):
    cfg = _config()
    command.upgrade(cfg, "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    assert set(_columns(conn, "event_summary")) == {"id", "event_id", "source_hash", "text"}
    assert set(_columns(conn, "story_summary")) == {
        "id", "story_id", "episode_id", "source_hash", "summary", "style"}
    conn.close()

    command.downgrade(cfg, "052069310f38")

    conn = sqlite3.connect(TEST_DB_PATH)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "event_summary" not in tables and "story_summary" not in tables
    conn.close()


def test_upgrade_inverts_sub_character_into_main_character(old_style_db):
    cfg = _config()
    command.upgrade(cfg, "24327ee59e1c")
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.execute("UPDATE character SET sub_character = (name = 'v0')")
    conn.commit()
    conn.close()

    command.upgrade(cfg, "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    assert "sub_character" not in _columns(conn)
    rows = dict(conn.execute("SELECT name, main_character FROM character").fetchall())
    assert rows["v0"] == 0
    assert {name for name, main in rows.items() if main} == set(rows) - {"v0"}
    conn.close()

    command.downgrade(cfg, "24327ee59e1c")

    conn = sqlite3.connect(TEST_DB_PATH)
    assert "main_character" not in _columns(conn)
    rows = dict(conn.execute("SELECT name, sub_character FROM character").fetchall())
    assert {name for name, sub in rows.items() if sub} == {"v0"}
    conn.close()


def test_upgrade_adds_event_seed_and_downgrade_drops_it(old_style_db):
    cfg = _config()
    command.upgrade(cfg, "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert set(_columns(conn, "event_seed")) == {"id", "text"}
    assert "event_seed_source" not in tables
    for table in ("story", "episode", "character", "event"):
        assert _columns(conn, table)["event_seeded"][:2] == ("BOOLEAN", 1), table
    conn.close()

    command.downgrade(cfg, "82c20d8db0c5")

    conn = sqlite3.connect(TEST_DB_PATH)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "event_seed" not in tables and "event_seed_source" not in tables
    assert "event_seeded" not in _columns(conn, "story")
    conn.close()


def test_upgrade_splits_seed_sources_into_id_columns_and_downgrade_joins_them(old_style_db):
    cfg = _config()
    command.upgrade(cfg, "cd51e8d34592")
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.executemany("INSERT INTO event_seed_source (id, source, source_id, source_hash) VALUES (?, ?, ?, 'h')",
                     [(1, "story", 5), (2, "episode", 6), (3, "character", 7)])
    conn.executemany("INSERT INTO event_seed (event_seed_source_id, text) VALUES (?, ?)",
                     [(1, "作品の種"), (2, "話の種"), (3, "人物の種")])
    conn.commit()
    conn.close()

    command.upgrade(cfg, "76fbe5ec1c2e")

    conn = sqlite3.connect(TEST_DB_PATH)
    rows = conn.execute("SELECT id, story_id, episode_id, character_id, event_id, source_hash "
                        "FROM event_seed_source ORDER BY id").fetchall()
    assert rows == [(1, 5, None, None, None, "h"), (2, None, 6, None, None, "h"), (3, None, None, 7, None, "h")]
    conn.execute("INSERT INTO event_seed_source (id, event_id, source_hash) VALUES (4, 8, 'h')")
    conn.execute("INSERT INTO event_seed (event_seed_source_id, text) VALUES (4, '出来事の種')")
    conn.commit()
    conn.close()

    command.downgrade(cfg, "cd51e8d34592")

    conn = sqlite3.connect(TEST_DB_PATH)
    rows = conn.execute("SELECT id, source, source_id FROM event_seed_source ORDER BY id").fetchall()
    assert rows == [(1, "story", 5), (2, "episode", 6), (3, "character", 7)]
    assert [row[0] for row in conn.execute("SELECT text FROM event_seed ORDER BY id")] == [
        "作品の種", "話の種", "人物の種"]
    conn.close()


def test_upgrade_flags_seeded_records_and_keeps_the_seeds(old_style_db):
    cfg = _config()
    command.upgrade(cfg, "76fbe5ec1c2e")
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.executemany("INSERT INTO story (id, name, narration, state, text) VALUES (?, '話', '', '構想中', '')",
                     [(1,), (2,)])
    conn.execute("INSERT INTO episode (id, story_id, title, synced, text) VALUES (1, 1, '一', 0, '')")
    conn.executemany("INSERT INTO event (id, name, hidden, time, text) VALUES (?, '出来事', 0, 0, '')",
                     [(1,), (2,)])
    conn.executemany("INSERT INTO event_seed_source (id, story_id, episode_id, character_id, event_id, source_hash) "
                     "VALUES (?, ?, ?, ?, ?, 'h')",
                     [(1, 1, None, None, None), (2, None, 1, None, None),
                      (3, None, None, 3, None), (4, None, None, None, 2)])
    conn.executemany("INSERT INTO event_seed (event_seed_source_id, text) VALUES (?, ?)",
                     [(1, "作品の種"), (4, "出来事の種")])
    conn.commit()
    conn.close()

    command.upgrade(cfg, "head")

    conn = sqlite3.connect(TEST_DB_PATH)
    flagged = {table: {row[0] for row in conn.execute(f'SELECT id FROM "{table}" WHERE event_seeded')}
               for table in ("story", "episode", "character", "event")}
    assert flagged == {"story": {1}, "episode": {1}, "character": {3}, "event": {2}}
    assert [row[0] for row in conn.execute("SELECT text FROM event_seed ORDER BY id")] == ["作品の種", "出来事の種"]
    conn.close()

    command.downgrade(cfg, "76fbe5ec1c2e")

    conn = sqlite3.connect(TEST_DB_PATH)
    assert conn.execute("SELECT count(*) FROM event_seed").fetchone() == (0,)
    assert "event_seeded" not in _columns(conn, "event")
    assert set(_columns(conn, "event_seed")) == {"id", "event_seed_source_id", "text"}
    conn.close()
