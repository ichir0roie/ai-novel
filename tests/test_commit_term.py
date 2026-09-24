"""語を確定する入口。JSON 文字列の下書きを受け、掛かる場所と上位の語の実在を検める。"""
import json

import pytest

from DEM.ai.claude_code.interface._base import UnknownFieldError, UnknownRecordError
from DEM.ai.claude_code.interface.randomizer.commit_term import CommitTerm
from DEM.db.schema import Location, Term


@pytest.fixture
def world(session):
    root = Location(name="世界線", kind="世界線", text="")
    session.add(root)
    session.commit()
    return root.id


def test_commit_from_json_string(session, world):
    draft = {"name": "外部デバイス", "kind": "技術", "restrict_world_id": world, "text": "身体アシスト技術"}
    result = CommitTerm(json.dumps(draft, ensure_ascii=False)).run()

    record = session.get(Term, result["id"])
    assert record.name == "外部デバイス" and record.kind == "技術"
    assert record.restrict_world_id == world and record.text == "身体アシスト技術"

    child = CommitTerm({"name": "寄生型", "kind": "技術", "parent_term_id": result["id"]}).run()
    assert session.get(Term, child["id"]).parent_term_id == result["id"]
    assert child["text"] == ""


@pytest.mark.parametrize("draft, message", [
    ({"kind": "技術"}, "name は必須"),
    ({"name": "語"}, "kind は必須"),
])
def test_commit_requires_name_and_kind(session, draft, message):
    with pytest.raises(ValueError, match=message):
        CommitTerm(draft).run()
    assert session.query(Term).count() == 0


def test_commit_rejects_unknown_references(session, world):
    with pytest.raises(UnknownRecordError, match="restrict_planet_id=999"):
        CommitTerm({"name": "語", "kind": "概念", "restrict_planet_id": 999}).run()
    with pytest.raises(UnknownRecordError, match="parent_term_id=999"):
        CommitTerm({"name": "語", "kind": "概念", "parent_term_id": 999}).run()
    with pytest.raises(UnknownFieldError):
        CommitTerm({"name": "語", "kind": "概念", "read": "ご"}).run()
    assert session.query(Term).count() == 0
