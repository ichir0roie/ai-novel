"""`import_db`: id 無しの md は採番された id を頭に付けた名前へ改名する。"""
import os

from DEM.db.schema import Location
from DEM.tool.markdown.import_db import import_db


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_name_only_file_is_renamed_with_assigned_id(session, tmp_path):
    root = str(tmp_path / "worlds")
    table_dir = os.path.join(root, "location")
    _write(os.path.join(table_dir, "新しい村.md"), "# data\n```json\n{\"kind\": \"村\"}\n```\n\n# text\n本文\n")
    _write(os.path.join(table_dir, "奥", "隠れ里.md"), "本文だけ\n")

    counts = import_db(root)
    assert counts["location"] == 2

    rows = {r.filename: r for r in session.query(Location).all()}
    assert set(rows) == {"新しい村", "隠れ里"}
    assert rows["新しい村"].text == "本文" and rows["新しい村"].kind == "村"
    assert rows["隠れ里"].directory_path == "奥"

    assert sorted(os.listdir(table_dir)) == [f"{rows['新しい村'].id}_新しい村.md", "奥"]
    assert os.listdir(os.path.join(table_dir, "奥")) == [f"{rows['隠れ里'].id}_隠れ里.md"]


def test_file_with_id_keeps_its_name(session, tmp_path):
    session.add(Location(id=7, name="古い村", kind="村", text="", filename="古い村"))
    session.commit()
    root = str(tmp_path / "worlds")
    table_dir = os.path.join(root, "location")
    _write(os.path.join(table_dir, "7_古い村.md"), "# data\n```json\n{\"kind\": \"村\"}\n```\n\n# text\n直した本文\n")

    import_db(root)

    assert os.listdir(table_dir) == ["7_古い村.md"]
    session.expire_all()
    assert session.get(Location, 7).text == "直した本文"


def test_fixed_sessions_ignore_env_db_path():
    from DEM.db.schema import get_env_session, get_novel_session, get_test_session

    def db_file(factory):
        with factory() as s:
            return os.path.basename(s.get_bind().url.database)

    assert db_file(get_env_session) == "novel.test.db"
    assert db_file(get_test_session) == "novel.test.db"
    assert db_file(get_novel_session) == "novel.db"


def test_novel_db_lives_in_parent_world_repo():
    from DEM.db.schema import NOVEL_DB_PATH
    from DEM.tool.markdown.export_db import WORLDS_ROOT as export_root
    from DEM.tool.markdown.import_db import WORLDS_ROOT as import_root

    assert os.path.normpath(NOVEL_DB_PATH) == os.path.normpath("../novel.db")
    assert export_root == import_root
    assert os.path.normpath(export_root) == os.path.normpath("../worlds")


def test_location_markdown_name_uses_name():
    assert Location(id=71, name="パンデム", text="").markdown_name == "71_パンデム.md"
    assert Location(id=72, text="").markdown_name == "72.md"
    assert Location(id=73, name="町", text="", filename="別名").markdown_name == "73_別名.md"


def test_import_location_id_only_file_gets_named_on_export(session, tmp_path):
    session.add(Location(id=71, name="パンデム", text=""))
    session.commit()
    root = str(tmp_path / "worlds")
    _write(os.path.join(root, "location", "71.md"), "# data\n```json\n{\"name\": \"パンデム\"}\n```\n\n# text\n本文\n")

    import_db(root)
    assert session.get(Location, 71).filename is None

    from DEM.tool.markdown.export_db import export_db
    export_db(root)
    assert sorted(os.listdir(os.path.join(root, "location"))) == ["71.md", "71_パンデム.md"]


def test_term_markdown_name_uses_name():
    from DEM.db.schema import Term

    assert Term(id=29, name="霊纏", kind="技術", text="").markdown_name == "29_霊纏.md"
    assert Term(id=30, name="語", kind="概念", text="", filename="別名").markdown_name == "30_別名.md"


def test_sync_paths_follow_env(tmp_path):
    import subprocess
    import sys

    env = dict(os.environ, DEM_NOVEL_DB_PATH=str(tmp_path / "a.db"), DEM_WORLDS_DIR=str(tmp_path / "w"))
    code = ("from DEM.db.schema import NOVEL_DB_PATH, get_novel_session;"
            "from DEM.tool.markdown.export_db import WORLDS_ROOT;"
            "print(NOVEL_DB_PATH); print(WORLDS_ROOT); print(get_novel_session().get_bind().url.database)")
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout.split()
    assert out == [str(tmp_path / "a.db"), str(tmp_path / "w"), str(tmp_path / "a.db")]
