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
