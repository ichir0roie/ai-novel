"""サブキャラクターフラグ(`Character.sub_character`)。出来事のランダム生成は
サブキャラクター(true)だけを対象にし、メインキャラクター(false)は外す。"""
from DEM.ai.time_keeper import event_progression_generator, main
from DEM.ai.time_keeper._export import export_step
from DEM.ai.time_keeper.random_character_generator import _generate_one
from DEM.data_access_logic.query.base import character_active_condition
from DEM.db.schema import Character, CharacterPlace, Location, Story
from DEM.db.stamp import Stamp
from DEM.tool.test.mock_ai_client import MockAIClient


def _place(session) -> Location:
    place = Location(name="村", kind="村", text="", start=Stamp(2000), active_random_generation=True)
    session.add(place)
    session.flush()
    session.add(Story(name="村の話", place_id=place.id, text="村の筋書き", narration="", state="構想中",
                      start=Stamp(2000), end=Stamp(2300)))
    session.commit()
    return place


def _character(session, place, *, sub_character: bool) -> Character:
    record = Character(name="仮名", text="", sub_character=sub_character, start=Stamp(2000))
    session.add(record)
    session.flush()
    session.add(CharacterPlace(character_id=record.id, location_id=place.id, start=Stamp(2000)))
    session.commit()
    return record


def test_character_active_condition_matches_sub_character_flag(session):
    place = _place(session)
    main_character = _character(session, place, sub_character=False)
    sub_character = _character(session, place, sub_character=True)

    ids = {row for row, in session.query(Character.id).filter(character_active_condition()).all()}
    assert ids == {sub_character.id}
    assert main_character.id not in ids


def test_group_by_place_keeps_only_sub_characters(session):
    place = _place(session)
    main_character = _character(session, place, sub_character=False)
    sub_character = _character(session, place, sub_character=True)

    grouped = event_progression_generator._group_by_place(session, Stamp(2100))

    ids = {c.id for c in grouped[place.id]}
    assert sub_character.id in ids
    assert main_character.id not in ids


def test_generated_character_is_marked_sub_character(session):
    place = _place(session)
    ai = MockAIClient(seed=1)

    record = _generate_one(session, place, Stamp(2100, 1, 1), __import__("random").Random(1), ai, person=True)

    assert record.sub_character is True


def test_export_step_writes_worlds_root(session, tmp_path):
    place = Location(name="村", kind="村", text="", start=Stamp(2000))
    session.add(place)
    session.commit()

    root = str(tmp_path / "worlds")
    export_step("test", root=root)

    import os
    assert os.path.isdir(os.path.join(root, "location"))


def test_loop_time_does_not_export_per_step(session, monkeypatch):
    place = _place(session)
    _character(session, place, sub_character=True)

    calls: list[str] = []
    monkeypatch.setattr(main, "export_step", lambda when: calls.append(when))
    monkeypatch.setattr(main.random, "randint", lambda a, b: 1)

    main.loop_time(MockAIClient(seed=2), start_time=Stamp(2100), max_days=3)

    assert calls == []
