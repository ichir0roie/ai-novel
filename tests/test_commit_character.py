"""人物・場所を確定する入口。JSON 文字列の下書きを受け、性格の段階と親の期間を検める。"""
import json

import pytest

from DEM.ai.claude_code.interface._base import UnknownFieldError
from DEM.ai.claude_code.interface.randomizer.commit_character import CommitCharacter
from DEM.ai.claude_code.interface.randomizer.commit_place import CommitPlace
from DEM.ai.claude_code.interface.randomizer.create_random_character import CreateRandomCharacter
from DEM.ai.claude_code.interface.randomizer.update_character import UpdateCharacter
from DEM.ai.claude_code.interface.story.update_story import UpdateStory
from DEM.ai.claude_code.interface.story.read_character import ReadCharacter
from DEM.db.schema import (
    PERSONALITY_COLUMNS, PERSONALITY_LEVELS, Character, CharacterPlace, Location, Story,
)
from DEM.db.stamp import Stamp


@pytest.fixture
def world(session):
    """期間の無い親(世界)と、その下に期間 2100〜2200 の村。どちらにも作品を置く。"""
    root = Location(name="世界", kind="世界", text="")
    session.add(root)
    session.flush()
    village = Location(name="村", kind="村", text="", parent_id=root.id,
                       start=Stamp(2100), end=Stamp(2200))
    session.add(village)
    session.flush()
    session.add(Story(name="世界の話", place_id=root.id, text="世界の筋書き", narration="", state="構想中"))
    session.add(Story(name="村の話", place_id=village.id, text="村の筋書き", narration="", state="構想中"))
    session.commit()
    return {"root": root.id, "village": village.id}


def _draft(**overrides) -> str:
    draft = CreateRandomCharacter().run()
    draft.update(overrides)
    return json.dumps(draft, ensure_ascii=False)


def test_commit_from_json_string(session, world):
    result = CommitCharacter(_draft(place_id=world["root"], start="2100", end="2160")).run()

    record = session.get(Character, result["id"])
    assert record.start == Stamp(2100) and record.end == Stamp(2160)
    assert all(getattr(record, name) in PERSONALITY_LEVELS for name in PERSONALITY_COLUMNS)
    assert {name: result[name] for name in PERSONALITY_COLUMNS} == {
        name: getattr(record, name) for name in PERSONALITY_COLUMNS}

    place = session.query(CharacterPlace).filter_by(character_id=record.id).one()
    assert place.location_id == world["root"]
    assert place.start == Stamp(2100)


def test_committed_character_is_a_sub_character_by_default(session, world):
    result = CommitCharacter(_draft(place_id=world["root"], start="2100")).run()

    assert session.get(Character, result["id"]).main_character is False


def test_commit_rejects_non_level_personality(session, world):
    with pytest.raises(ValueError, match="無/低/並/高/必"):
        CommitCharacter(_draft(place_id=world["root"], start="2100", sincerity=0)).run()
    assert session.query(Character).count() == 0


def test_commit_rejects_unknown_field(world):
    with pytest.raises(UnknownFieldError):
        CommitCharacter(_draft(place_id=world["root"], start="2100", charisma="高")).run()


def test_commit_requires_story_on_place(session):
    lonely = Location(name="孤島", kind="島", text="")
    session.add(lonely)
    session.commit()
    with pytest.raises(ValueError, match="作品が無い"):
        CommitCharacter(_draft(place_id=lonely.id, start="2100")).run()


def test_no_character_cap_per_place(session, world):
    for _ in range(7):
        CommitCharacter(_draft(place_id=world["village"], start="2101", end="2150")).run()
    assert session.query(CharacterPlace).filter_by(location_id=world["village"]).count() == 7


@pytest.mark.parametrize("start, end, message", [
    ("2300", None, "end=2200/01/01 00:00:00 以後"),
    ("2150", "2250", "end=2200/01/01 00:00:00 を超える"),
    ("2050", "2150", "start=2100/01/01 00:00:00 より前"),
])
def test_commit_rejects_span_outside_parent(session, world, start, end, message):
    with pytest.raises(ValueError, match=message):
        CommitCharacter(_draft(place_id=world["village"], start=start, end=end)).run()
    assert session.query(Character).count() == 0


@pytest.mark.parametrize("start, end", [
    ("2100", "2200"),
    ("2150", "2190"),
    ("2150", None),
    (None, None),
])
def test_commit_accepts_span_inside_parent(world, start, end):
    result = CommitCharacter(_draft(place_id=world["village"], start=start, end=end)).run()
    assert result["id"] is not None


def test_commit_without_parent_span_accepts_any_time(world):
    result = CommitCharacter(_draft(place_id=world["root"], start="1", end="9999")).run()
    assert result["start"] == "1/01/01 00:00:00"


def test_update_personality(session, world):
    committed = CommitCharacter(_draft(place_id=world["root"], start="2100")).run()

    updated = UpdateCharacter({"id": committed["id"], "curiosity": "必"}).run()
    assert updated["curiosity"] == "必"
    session.expire_all()
    assert session.get(Character, committed["id"]).curiosity == "必"

    for bad in ({"id": committed["id"], "curiosity": 3},
                {"id": committed["id"], "sincerity": "中"}):
        with pytest.raises(ValueError, match="無/低/並/高/必"):
            UpdateCharacter(bad).run()
    session.expire_all()
    assert session.get(Character, committed["id"]).sincerity == committed["sincerity"]


def test_update_accepts_stamp_string_with_five_digit_year(session, world):
    committed = CommitCharacter(_draft(place_id=world["root"], start="2100")).run()

    updated = UpdateCharacter({"id": committed["id"], "start": "11556/01/01 00:00:00"}).run()
    assert updated["start"] == "11556/01/01 00:00:00"
    session.expire_all()
    assert session.get(Character, committed["id"]).start == Stamp(11556)

    story_id = session.query(Story).filter_by(place_id=world["root"]).one().id
    updated = UpdateStory({"id": story_id, "start": "11572"}).run()
    assert updated["start"] == "11572/01/01 00:00:00"
    session.expire_all()
    assert session.get(Story, story_id).start == Stamp(11572)


def test_update_requires_id():
    with pytest.raises(ValueError, match="id は必須"):
        UpdateCharacter({"curiosity": "必"}).run()


def test_read_character_returns_levels(world):
    committed = CommitCharacter(
        _draft(place_id=world["root"], start="2100", sincerity="無", imagination="必")).run()
    sheet = ReadCharacter(committed["id"]).run()
    assert sheet["sincerity"] == "無" and sheet["imagination"] == "必"
    assert sheet["place"]["place_id"] == world["root"]


def test_commit_place_from_json_string_checks_parent_span(session, world):
    inside = {"name": "集落", "kind": "集落", "text": "", "parent_id": world["village"],
              "start": "2120", "end": "2180"}
    result = CommitPlace(json.dumps(inside, ensure_ascii=False)).run()
    assert session.get(Location, result["id"]).start == Stamp(2120)

    outside = dict(inside, name="はみ出す集落", end="2250")
    with pytest.raises(ValueError, match="end=2200/01/01 00:00:00 を超える"):
        CommitPlace(json.dumps(outside, ensure_ascii=False)).run()
