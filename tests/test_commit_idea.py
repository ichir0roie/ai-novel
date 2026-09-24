import json

import pytest

from ai.claude_code.interface._base import UnknownFieldError, UnknownRecordError
from ai.claude_code.interface.randomizer.commit_idea import CommitIdea
from db.schema import Idea, Location


@pytest.fixture
def world(session):
    root = Location(name="世界線", kind="世界線", text="")
    session.add(root)
    session.commit()
    return root.id


def test_commit_from_json_string(session, world):
    draft = {"name": "外部デバイス", "kind": "技術", "restrict_world_id": world, "text": "身体アシスト技術"}
    result = CommitIdea(json.dumps(draft, ensure_ascii=False)).run()

    record = session.get(Idea, result["id"])
    assert record.name == "外部デバイス" and record.kind == "技術"
    assert record.restrict_world_id == world and record.text == "身体アシスト技術"

    child = CommitIdea({"name": "寄生型", "kind": "技術", "parent_idea_id": result["id"]}).run()
    assert session.get(Idea, child["id"]).parent_idea_id == result["id"]
    assert child["text"] == ""


@pytest.mark.parametrize("draft, message", [
    ({"kind": "技術"}, "name は必須"),
    ({"name": "アイデア"}, "kind は必須"),
])
def test_commit_requires_name_and_kind(session, draft, message):
    with pytest.raises(ValueError, match=message):
        CommitIdea(draft).run()
    assert session.query(Idea).count() == 0


def test_commit_rejects_unknown_references(session, world):
    with pytest.raises(UnknownRecordError, match="restrict_planet_id=999"):
        CommitIdea({"name": "アイデア", "kind": "概念", "restrict_planet_id": 999}).run()
    with pytest.raises(UnknownRecordError, match="parent_idea_id=999"):
        CommitIdea({"name": "アイデア", "kind": "概念", "parent_idea_id": 999}).run()
    with pytest.raises(UnknownFieldError):
        CommitIdea({"name": "アイデア", "kind": "概念", "read": "ご"}).run()
    assert session.query(Idea).count() == 0
