"""人物同士の相関(`character_relation`): 確定・修正・一覧の入口と、`export_db` が書く md・HTML、`import_db` の読み戻し。"""
import json
import os

import pytest

from DEM.ai.claude_code.interface._base import UnknownFieldError, UnknownRecordError
from DEM.ai.claude_code.interface.randomizer.commit_character_relation import CommitCharacterRelation
from DEM.ai.claude_code.interface.randomizer.update_character_relation import UpdateCharacterRelation
from DEM.ai.claude_code.interface.world.list_character_relations import ListCharacterRelations
from DEM.db.schema import Character, CharacterRelation
from DEM.db.stamp import Stamp
from DEM.tool.markdown.export_db import export_db
from DEM.tool.markdown.import_db import import_db


@pytest.fixture
def people(session):
    rows = [Character(name="娘", kind="人物", text=""), Character(name="母", kind="人物", text=""),
            Character(name="裁きの座", kind="組織", text="")]
    session.add_all(rows)
    session.commit()
    return {"daughter": rows[0].id, "mother": rows[1].id, "court": rows[2].id}


def test_commit_and_list(session, people):
    result = CommitCharacterRelation(json.dumps({
        "character_id_1": people["mother"], "character_id_2": people["daughter"],
        "relation": "母", "start": "11572", "end": "11582",
        "text": "地上で十年を共に暮らす。"}, ensure_ascii=False)).run()
    assert result["relation"] == "母" and result["id"] is not None
    assert result["start"] == "11572/01/01 00:00:00" and result["end"] == "11582/01/01 00:00:00"
    CommitCharacterRelation({"character_id_1": people["court"], "character_id_2": people["mother"],
                             "relation": "所属先"}).run()

    record = session.get(CharacterRelation, result["id"])
    assert (record.character_id_1, record.character_id_2) == (people["mother"], people["daughter"])
    assert record.text == "地上で十年を共に暮らす。"
    assert record.start == Stamp(11572) and record.end == Stamp(11582)

    rows = ListCharacterRelations().run()
    assert [r["relation"] for r in rows] == ["母", "所属先"]
    rows = ListCharacterRelations(people["daughter"]).run()
    assert [r["relation"] for r in rows] == ["母"]
    assert ListCharacterRelations(people["court"]).run()[0]["text"] == ""


def test_commit_rejects_bad_input(session, people):
    base = {"character_id_1": people["mother"], "character_id_2": people["daughter"], "relation": "母"}
    with pytest.raises(ValueError, match="relation は必須"):
        CommitCharacterRelation({**base, "relation": ""}).run()
    with pytest.raises(ValueError, match="別の人物"):
        CommitCharacterRelation({**base, "character_id_2": people["mother"]}).run()
    with pytest.raises(UnknownRecordError):
        CommitCharacterRelation({**base, "character_id_2": 9999}).run()
    with pytest.raises(UnknownFieldError):
        CommitCharacterRelation({**base, "strength": 3}).run()
    assert session.query(CharacterRelation).count() == 0


def test_update(session, people):
    created = CommitCharacterRelation({"character_id_1": people["mother"], "character_id_2": people["daughter"],
                                       "relation": "母"}).run()
    result = UpdateCharacterRelation({"id": created["id"], "relation": "生みの母", "text": "本文"}).run()
    assert result["relation"] == "生みの母"
    session.expire_all()
    assert session.get(CharacterRelation, created["id"]).text == "本文"

    with pytest.raises(ValueError, match="id は必須"):
        UpdateCharacterRelation({"relation": "x"}).run()
    with pytest.raises(ValueError, match="見つからない"):
        UpdateCharacterRelation({"id": 9999, "relation": "x"}).run()
    with pytest.raises(ValueError, match="別の人物"):
        UpdateCharacterRelation({"id": created["id"], "character_id_2": people["mother"]}).run()


def test_export_writes_markdown_and_html(session, people, tmp_path):
    session.add(CharacterRelation(character_id_1=people["mother"], character_id_2=people["daughter"],
                                  relation="母", text="共に暮らす。\n二行目。", start=Stamp(11572), end=Stamp(11582)))
    session.commit()
    root = str(tmp_path / "worlds")
    counts = export_db(root)
    assert counts["character_relation"] == 1

    table_dir = os.path.join(root, "character_relation")
    md_files = [n for n in os.listdir(table_dir) if n.endswith(".md")]
    assert len(md_files) == 1
    with open(os.path.join(table_dir, md_files[0]), encoding="utf-8") as f:
        md = f.read()
    assert '"relation": "母"' in md and "# text\n共に暮らす。\n二行目。" in md
    assert '"start": "11572/01/01 00:00:00"' in md

    with open(os.path.join(table_dir, "relation.html"), encoding="utf-8") as f:
        html = f.read()
    assert '"name": "裁きの座"' in html and '"relation": "母"' in html
    assert '"start": 11572, "end": 11582' in html
    assert "</script>" in html and "<\\/" in html or "</" not in json.dumps("x")


def test_export_without_relations_still_writes_html(session, people, tmp_path):
    root = str(tmp_path / "worlds")
    export_db(root)
    with open(os.path.join(root, "character_relation", "relation.html"), encoding="utf-8") as f:
        html = f.read()
    assert '"relations": []' in html and '"name": "娘"' in html


def test_import_reads_relation_back(session, people, tmp_path):
    root = str(tmp_path / "worlds")
    table_dir = os.path.join(root, "character_relation")
    os.makedirs(table_dir)
    data = {"character_id_1": people["daughter"], "character_id_2": people["court"], "relation": "追われる側",
            "start": "11582", "end": None}
    with open(os.path.join(table_dir, "娘と座.md"), "w", encoding="utf-8") as f:
        f.write(f"# data\n```json\n{json.dumps(data, ensure_ascii=False)}\n```\n\n# text\n帳のどこにも入らない。\n")

    counts = import_db(root)
    assert counts["character_relation"] == 1
    row = session.query(CharacterRelation).one()
    assert (row.character_id_1, row.character_id_2, row.relation) == (people["daughter"], people["court"], "追われる側")
    assert row.text == "帳のどこにも入らない。" and row.filename == "娘と座"
    assert row.start == Stamp(11582) and row.end is None
    assert os.listdir(table_dir) == [f"{row.id}_娘と座.md"]
