import json
import os

import pytest

from db.schema import PERSONALITY_DEFAULT, Character, CharacterParameter, resolve_parameters
from db.stamp import Stamp
from tool.markdown.export_db import export_db
from tool.markdown.import_db import ImportDbError, import_db


def _row(id_, start=None, end=None, **values):
    return CharacterParameter(id=id_, start=Stamp.parse(start), end=Stamp.parse(end), **values)


def test_row_without_start_and_end_covers_every_time():
    rows = [_row(1, height=140.0, sincerity="低")]
    for time in (Stamp(1), Stamp(11592), None):
        values = resolve_parameters(rows, time)
        assert values["height"] == 140.0 and values["sincerity"] == "低"


def test_period_row_overrides_only_its_own_columns_within_its_period():
    rows = [
        _row(1, height=140.0, tone="大声", sincerity="低"),
        _row(2, start="11600", height=175.0),
        _row(3, start="11610", end="11620", tone="気さく"),
    ]
    before = resolve_parameters(rows, Stamp(11599, 12, 31))
    assert (before["height"], before["tone"]) == (140.0, "大声")

    grown = resolve_parameters(rows, Stamp(11600))
    assert (grown["height"], grown["tone"], grown["sincerity"]) == (175.0, "大声", "低")

    assert resolve_parameters(rows, Stamp(11615))["tone"] == "気さく"
    # end の時刻からは効かない
    assert resolve_parameters(rows, Stamp(11620))["tone"] == "大声"


def test_without_time_only_rows_covering_every_time_apply():
    rows = [_row(1, height=140.0), _row(2, start="11600", height=175.0), _row(3, end="11500", sex="女")]
    values = resolve_parameters(rows, None)
    assert values["height"] == 140.0 and values["sex"] is None


def test_narrower_and_later_rows_win():
    rows = [
        _row(1, start="11600", end="11700", tone="二端"),
        _row(2, start="11600", tone="始まりだけ"),
        _row(3, tone="全期間"),
    ]
    assert resolve_parameters(rows, Stamp(11650))["tone"] == "二端"
    later = rows + [_row(4, start="11640", tone="遅い始まり")]
    assert resolve_parameters(later, Stamp(11650))["tone"] == "二端"
    assert resolve_parameters(later[1:], Stamp(11650))["tone"] == "遅い始まり"


def test_family_name_changes_from_its_period():
    rows = [_row(1, family_name="ベルク"), _row(2, start="11600", family_name="ロウ")]
    assert resolve_parameters(rows, Stamp(11599))["family_name"] == "ベルク"
    assert resolve_parameters(rows, Stamp(11600))["family_name"] == "ロウ"


def test_unset_personality_falls_back_to_default():
    values = resolve_parameters([_row(1, start="11600", curiosity="必")], Stamp(11500))
    assert values["curiosity"] == PERSONALITY_DEFAULT and values["tone"] is None


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _read_data(path) -> dict:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return json.loads(content.split("```json\n", 1)[1].split("\n```", 1)[0])


def test_parameters_round_trip_through_character_markdown(session, tmp_path):
    session.add(Character(id=7, name="ラファル", text="本文", parameters=[
        CharacterParameter(height=140.0, sincerity="並"),
        CharacterParameter(start=Stamp(11600), height=175.0),
    ]))
    session.commit()
    root = str(tmp_path / "worlds")

    export_db(root)
    path = os.path.join(root, "character", "7_ラファル.md")
    data = _read_data(path)
    assert "height" not in data
    assert [(item["start"], item["end"], item["height"]) for item in data["parameters"]] == [
        (None, None, 140.0), ("11600/01/01 00:00:00", None, 175.0)]
    assert "id" not in data["parameters"][0] and "character_id" not in data["parameters"][0]

    ids = [row.id for row in session.get(Character, 7).parameters]
    data["parameters"][1]["tone"] = "気さく"
    data["parameters"].append({"start": "11610", "end": "11620", "sincerity": "高"})
    _write(path, f"# data\n```json\n{json.dumps(data, ensure_ascii=False)}\n```\n\n# text\n本文\n")
    import_db(root)

    session.expire_all()
    record = session.get(Character, 7)
    assert [row.id for row in record.parameters][:2] == ids
    assert record.parameters_at(Stamp(11615))["sincerity"] == "高"
    assert record.parameters_at(Stamp(11605))["tone"] == "気さく"

    data["parameters"] = data["parameters"][:1]
    _write(path, f"# data\n```json\n{json.dumps(data, ensure_ascii=False)}\n```\n\n# text\n本文\n")
    import_db(root)
    session.expire_all()
    assert [row.id for row in session.get(Character, 7).parameters] == ids[:1]
    assert session.query(CharacterParameter).count() == 1


@pytest.mark.parametrize("parameters, message", [
    ([{"charisma": "高"}], "スキーマに無い欄"),
    ([{"sincerity": "中"}], "無/低/並/高/必"),
    ({"sincerity": "高"}, "配列"),
])
def test_import_rejects_bad_parameters(tmp_path, parameters, message):
    root = str(tmp_path / "worlds")
    data = {"name": "x", "parameters": parameters}
    _write(os.path.join(root, "character", "x.md"),
           f"# data\n```json\n{json.dumps(data, ensure_ascii=False)}\n```\n\n# text\n\n")
    with pytest.raises(ValueError, match=message):
        import_db(root)
