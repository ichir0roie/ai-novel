"""人物の居場所を確定する入口。人物と場所の実在と、場所の期間に収まるかを検める。"""
import pytest

from DEM.ai.claude_code.interface._base import UnknownRecordError
from DEM.ai.claude_code.interface.randomizer.commit_character_place import CommitCharacterPlace
from DEM.db.schema import Character, CharacterPlace, Location
from DEM.db.stamp import Stamp


@pytest.fixture
def world(session):
    village = Location(name="村", kind="村", text="", start=Stamp(2100), end=Stamp(2200))
    person = Character(name="人", kind="人物", text="")
    session.add_all([village, person])
    session.commit()
    return {"village": village.id, "person": person.id}


def test_commit_adds_place_for_existing_character(session, world):
    result = CommitCharacterPlace({
        "character_id": world["person"], "location_id": world["village"], "start": "2120"}).run()

    row = session.get(CharacterPlace, result["id"])
    assert row.character_id == world["person"] and row.location_id == world["village"]
    assert row.start == Stamp(2120) and result["start"] == "2120/01/01 00:00:00"


def test_commit_rejects_span_outside_place(session, world):
    with pytest.raises(ValueError, match="end=2200/01/01 00:00:00 以後"):
        CommitCharacterPlace({
            "character_id": world["person"], "location_id": world["village"], "start": "2300"}).run()
    assert session.query(CharacterPlace).count() == 0


def test_commit_rejects_unknown_or_missing_references(session, world):
    with pytest.raises(ValueError, match="character_id は必須"):
        CommitCharacterPlace({"location_id": world["village"]}).run()
    with pytest.raises(UnknownRecordError, match="character_id=999"):
        CommitCharacterPlace({"character_id": 999, "location_id": world["village"]}).run()
    with pytest.raises(UnknownRecordError, match="location_id=999"):
        CommitCharacterPlace({"character_id": world["person"], "location_id": 999}).run()
    assert session.query(CharacterPlace).count() == 0
