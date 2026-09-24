"""出来事の入口(`ListEvents` / `ReadEvents`)が返す辞書。"""
from DEM.ai.claude_code.interface.story.read_events import ReadEvents
from DEM.ai.claude_code.interface.world.list_events import ListEvents
from DEM.db.schema import Event, Location
from DEM.db.stamp import Stamp


def _event_at(session, place) -> Event:
    record = Event(name="出来事", text="本文", time=Stamp(2100), start=Stamp(2100),
                   end=Stamp(2100, 1, 2), location_id=None if place is None else place.id)
    session.add(record)
    session.commit()
    return record


def test_event_row_has_the_name_of_its_place(session):
    place = Location(name="村", kind="村", text="山あいの村", start=Stamp(2000))
    session.add(place)
    session.commit()
    event = _event_at(session, place)

    (row,) = ListEvents().run()
    (by_place,) = ReadEvents(record_id=place.id).run()

    assert row["id"] == event.id
    assert row["place_name"] == "村"
    assert by_place["place_name"] == "村"


def test_event_row_without_place_has_no_place_name(session):
    _event_at(session, None)

    (row,) = ListEvents().run()

    assert row["place_name"] is None
