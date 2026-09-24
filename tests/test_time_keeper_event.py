"""event_progression_generator の、出来事の偏りを抑えるための仕組み。"""
from ai.instructions.event_writing import (
    CHARACTER_TEXT_UPDATE_INSTRUCTION, EVENT_PROGRESSION_INSTRUCTION,
)
from ai.instructions.naming import CHARACTER_NAMING_INSTRUCTION
from ai.time_keeper import constants
from ai.time_keeper._format import add_days
from ai.time_keeper.event_progression_generator import _place_roll_probability
from db.schema import Event, Location
from db.stamp import Stamp


def _place(session) -> Location:
    place = Location(name="村", kind="村", text="山あいの村", start=Stamp(2000))
    session.add(place)
    session.flush()
    return place


def test_place_roll_probability_is_default_without_recent_event(session):
    place = _place(session)
    probability = _place_roll_probability(session, place.id, Stamp(2100, 1, 1))
    assert probability == constants.PLACE_PROBABILITY


def test_place_roll_probability_is_lowered_right_after_an_event(session):
    place = _place(session)
    session.add(Event(
        name="出来事", text="", location_id=place.id,
        time=Stamp(2100, 1, 1), start=Stamp(2100, 1, 1), end=Stamp(2100, 1, 1)))
    session.commit()

    probability = _place_roll_probability(session, place.id, Stamp(2100, 2, 1))

    assert probability == constants.PLACE_PROBABILITY * constants.PLACE_PROBABILITY_COOLDOWN_FACTOR


def test_place_roll_probability_recovers_after_cooldown(session):
    place = _place(session)
    session.add(Event(
        name="出来事", text="", location_id=place.id,
        time=Stamp(2100, 1, 1), start=Stamp(2100, 1, 1), end=Stamp(2100, 1, 1)))
    session.commit()

    cooldown_end = add_days(Stamp(2100, 1, 1), int(constants.PLACE_COOLDOWN_MONTHS * 30))
    probability = _place_roll_probability(session, place.id, cooldown_end)

    assert probability == constants.PLACE_PROBABILITY


def test_event_progression_instruction_warns_against_reusing_wording():
    assert "同じ形容表現を繰り返し出来事の軸に据えない" in EVENT_PROGRESSION_INSTRUCTION


def test_character_text_update_instruction_warns_against_reusing_wording():
    assert "繰り返さない" in CHARACTER_TEXT_UPDATE_INSTRUCTION


def test_character_naming_instruction_refers_to_the_passed_name_list():
    assert "既にいる人物・対象の名" in CHARACTER_NAMING_INSTRUCTION
