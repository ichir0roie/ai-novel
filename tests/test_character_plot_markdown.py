"""`character_plot` の md 名は `{id}_{start}_{end}_{name}.md`。import はその名前から start/end/name を読み戻す。"""
import os

from DEM.db.schema import Character, CharacterPlot
from DEM.db.stamp import Stamp
from DEM.tool.markdown.export_db import export_db
from DEM.tool.markdown.import_db import import_db


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _character(session):
    c = Character(name="ノア", text="")
    session.add(c)
    session.commit()
    return c


def test_markdown_name_has_start_end_and_name():
    plot = CharacterPlot(id=3, character_id=1, text="", filename="誕生",
                         start=Stamp(1572), end=Stamp(1575, 3, 5))
    assert plot.markdown_name == "3_1572_1575-03-05_誕生.md"
    assert CharacterPlot(id=4, character_id=1, text="").markdown_name == "4__.md"
    assert CharacterPlot(id=5, character_id=1, text="", start=Stamp(1572, 1, 1, 9, 30)).markdown_name == "5_1572-01-01T093000_.md"
    assert CharacterPlot(id=6, character_id=1, text="", filename="誕生").markdown_name == "6___誕生.md"


def test_parse_markdown_stem():
    assert CharacterPlot.parse_markdown_stem("3_1572_1575_誕生") == (
        3, {"start": Stamp(1572), "end": Stamp(1575), "filename": "誕生"})
    assert CharacterPlot.parse_markdown_stem("1572_1575_誕生") == (
        None, {"start": Stamp(1572), "end": Stamp(1575), "filename": "誕生"})
    assert CharacterPlot.parse_markdown_stem("4__") == (4, {"start": None, "end": None, "filename": None})
    assert CharacterPlot.parse_markdown_stem("6___誕生") == (6, {"start": None, "end": None, "filename": "誕生"})
    assert CharacterPlot.parse_markdown_stem("5_1572-01-01T093000__幼少_前") == (
        5, {"start": Stamp(1572, 1, 1, 9, 30), "end": None, "filename": "幼少_前"})
    assert CharacterPlot.parse_markdown_stem("7_誕生") == (7, {"start": None, "end": None, "filename": "誕生"})
    assert CharacterPlot.parse_markdown_stem("誕生") == (None, {"start": None, "end": None, "filename": "誕生"})


def test_export_writes_start_end_in_name_and_data(session, tmp_path):
    c = _character(session)
    session.add(CharacterPlot(character_id=c.id, text="本文", filename="誕生", start=Stamp(1572), end=Stamp(1575)))
    session.commit()
    plot_id = session.query(CharacterPlot).one().id

    export_db(str(tmp_path / "worlds"))

    table_dir = tmp_path / "worlds" / "character_plot"
    assert os.listdir(table_dir) == [f"{plot_id}_1572_1575_誕生.md"]
    content = (table_dir / f"{plot_id}_1572_1575_誕生.md").read_text(encoding="utf-8")
    assert '"start": "1572/01/01 00:00:00"' in content and '"end": "1575/01/01 00:00:00"' in content
    assert f'"character_id": {c.id}' in content


def test_export_writes_null_columns_in_data(session, tmp_path):
    c = _character(session)
    session.add(CharacterPlot(character_id=c.id, text="本文", filename="幼少"))
    session.commit()
    plot_id = session.query(CharacterPlot).one().id

    export_db(str(tmp_path / "worlds"))

    content = (tmp_path / "worlds" / "character_plot" / f"{plot_id}___幼少.md").read_text(encoding="utf-8")
    assert '"start": null' in content and '"end": null' in content
    assert f'"character_id": {c.id}' in content


def test_import_reads_start_end_from_name_and_renames(session, tmp_path):
    c = _character(session)
    root = str(tmp_path / "worlds")
    table_dir = os.path.join(root, "character_plot", "ノア")
    _write(os.path.join(table_dir, "1572_1575_誕生.md"),
           f"# data\n```json\n{{\"character_id\": {c.id}}}\n```\n\n# text\n本文\n")

    assert import_db(root)["character_plot"] == 1

    plot = session.query(CharacterPlot).one()
    assert (plot.start, plot.end, plot.filename, plot.directory_path) == (Stamp(1572), Stamp(1575), "誕生", "ノア")
    assert os.listdir(table_dir) == [f"{plot.id}_1572_1575_誕生.md"]


def test_import_name_overrides_dates_of_existing_row(session, tmp_path):
    c = _character(session)
    session.add(CharacterPlot(id=9, character_id=c.id, text="", start=Stamp(1572), end=Stamp(1575)))
    session.commit()
    root = str(tmp_path / "worlds")
    table_dir = os.path.join(root, "character_plot")
    _write(os.path.join(table_dir, "9_1576_1586_幼少.md"),
           f"# data\n```json\n{{\"character_id\": {c.id}}}\n```\n\n# text\n直した本文\n")

    import_db(root)

    session.expire_all()
    plot = session.get(CharacterPlot, 9)
    assert (plot.start, plot.end, plot.filename, plot.text) == (Stamp(1576), Stamp(1586), "幼少", "直した本文")
    assert os.listdir(table_dir) == ["9_1576_1586_幼少.md"]


def test_import_name_only_file_registers_null_dates(session, tmp_path):
    c = _character(session)
    session.add(CharacterPlot(id=9, character_id=c.id, text="", start=Stamp(1572), end=Stamp(1575)))
    session.commit()
    root = str(tmp_path / "worlds")
    table_dir = os.path.join(root, "character_plot")
    _write(os.path.join(table_dir, "誕生.md"), f"# data\n```json\n{{\"character_id\": {c.id}}}\n```\n\n# text\n本文\n")
    _write(os.path.join(table_dir, "9_幼少.md"), f"# data\n```json\n{{\"character_id\": {c.id}}}\n```\n\n# text\n本文\n")

    assert import_db(root)["character_plot"] == 2

    session.expire_all()
    new = session.query(CharacterPlot).filter(CharacterPlot.filename == "誕生").one()
    assert (new.start, new.end) == (None, None)
    old = session.get(CharacterPlot, 9)
    assert (old.start, old.end, old.filename) == (None, None, "幼少")
    assert sorted(os.listdir(table_dir)) == sorted([f"{new.id}___誕生.md", "9_幼少.md"])
