"""`randomizer/` の入口のうち、出来事の確定・下書きと、場所の下書き・削除。"""
import pytest

from DEM.ai.claude_code.interface._base import UnknownFieldError, UnknownRecordError
from DEM.ai.claude_code.interface.randomizer.commit_event import CommitEvent
from DEM.ai.claude_code.interface.randomizer.create_random_event import CreateRandomEvent
from DEM.ai.claude_code.interface.randomizer.create_random_place import CreateRandomPlace
from DEM.ai.claude_code.interface.randomizer.delete_place import DeletePlace
from DEM.db.schema import Character, Event, EventCharacter, Location


@pytest.fixture
def place(session):
    location = Location(name="村", kind="村", text="")
    session.add(location)
    session.commit()
    return location.id


@pytest.fixture
def character(session):
    record = Character(name="アル", text="")
    session.add(record)
    session.commit()
    return record.id


def test_create_random_event_is_a_draft_with_overrides():
    draft = CreateRandomEvent(name="祭り", location_id=3).run()
    assert draft["name"] == "祭り"
    assert draft["location_id"] == 3
    assert draft["character_ids"] == []
    assert "id" not in draft


def test_create_random_event_does_not_share_character_ids():
    first = CreateRandomEvent().run()
    first["character_ids"].append(1)
    assert CreateRandomEvent().run()["character_ids"] == []


def test_create_random_place_is_a_draft_with_overrides():
    draft = CreateRandomPlace(name="港町", parent_id=2).run()
    assert draft["name"] == "港町"
    assert draft["parent_id"] == 2
    assert "id" not in draft


def test_commit_event_writes_characters(session, place, character):
    event = CommitEvent({"id": 99, "name": "祭り", "text": "", "time": "2100/01/01 00:00:00",
                         "location_id": place, "character_ids": [character]}).run()
    assert event["id"] != 99  # id は採番に任せる
    assert event["name"] == "祭り"
    assert event["character_ids"] == [character]
    assert str(event["time"]) == "2100/01/01 00:00:00"

    links = session.query(EventCharacter).all()
    assert [(link.event_id, link.character_id) for link in links] == [(event["id"], character)]


def test_commit_event_accepts_json_string(place):
    event = CommitEvent('{"name": "市", "text": "", "time": "2100", "location_id": %d}' % place).run()
    assert event["name"] == "市"
    assert event["character_ids"] == []


@pytest.mark.parametrize("payload", [
    {"time": "2100"},
    {"name": "", "time": "2100"},
    {"name": "時の無い出来事"},
])
def test_commit_event_requires_name_and_time(payload):
    with pytest.raises(ValueError):
        CommitEvent(payload).run()


def test_commit_event_rejects_unknown_field():
    with pytest.raises(UnknownFieldError):
        CommitEvent({"name": "祭り", "time": "2100", "weather": "晴れ"}).run()


@pytest.mark.parametrize("field", ["location_id", "parent_event_id"])
def test_commit_event_rejects_unknown_reference(session, field):
    with pytest.raises(UnknownRecordError):
        CommitEvent({"name": "祭り", "time": "2100", field: 9999}).run()
    assert session.query(Event).count() == 0


def test_commit_event_rejects_unknown_character(session, place, character):
    with pytest.raises(UnknownRecordError):
        CommitEvent({"name": "祭り", "time": "2100", "location_id": place,
                     "character_ids": [character, 9999]}).run()
    assert session.query(Event).count() == 0


def test_delete_place_returns_deleted_row(session, place):
    deleted = DeletePlace(place).run()
    assert deleted == {"id": place, "name": "村", "kind": "村"}
    session.expire_all()
    assert session.get(Location, place) is None


def test_delete_place_refuses_place_with_children(session, place):
    session.add(Location(name="家", kind="建物", text="", parent_id=place))
    session.commit()
    with pytest.raises(ValueError):
        DeletePlace(place).run()
    session.expire_all()
    assert session.get(Location, place) is not None


def test_delete_place_rejects_unknown_id():
    with pytest.raises(UnknownRecordError):
        DeletePlace(9999).run()
