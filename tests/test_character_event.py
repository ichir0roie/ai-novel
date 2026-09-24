"""毎日のルーチン(`character_event_generator`)。ランダムに選んだサブキャラクターの、最新の出来事の次の出来事を起こす。"""
import random

from DEM.ai.instructions.event_writing import EVENT_NOVEL_INSTRUCTION, EVENT_RECORD_INSTRUCTION
from DEM.ai.time_keeper import (
    character_event_generator, event_progression_generator, event_seed, event_summary, main,
)
from DEM.ai.time_keeper._format import days_between
from DEM.data_access_logic.query import common_query
from DEM.db.schema import (
    Character, CharacterPlace, Event, EventCharacter, EventSeed, EventSummary, Location, Story,
    summary_source_hash,
)
from DEM.db.stamp import Stamp
from DEM.tool.test.mock_ai_client import MockAIClient

STORY_START = Stamp(2100, 4, 1)


class _NoShuffle(random.Random):
    """候補を id 順のまま回す(誰が主役になるかをテストで決める)。"""

    def shuffle(self, x):
        pass


class _LeavesEveryoneOut(MockAIClient):
    def try_generate_json(self, prompt, schema, **kwargs):
        decided = super().try_generate_json(prompt, schema, **kwargs)
        if schema is event_progression_generator._PLACE_SCHEMA:
            decided["character_ids"] = []
        return decided


def _place(session, *, active=True) -> Location:
    place = Location(name="村", kind="村", text="山あいの村", start=Stamp(2000),
                     active_random_generation=active)
    session.add(place)
    session.flush()
    session.add(Story(name="村の話", place_id=place.id, text="村の筋書き", narration="", state="構想中",
                      start=STORY_START, end=Stamp(2300)))
    session.commit()
    return place


def _character(session, place, name="甲", *, main_character=False, start=Stamp(2080), end=None) -> Character:
    record = Character(name=name, text=f"{name}の説明", main_character=main_character,
                       start=start, end=end)
    session.add(record)
    session.flush()
    if place is not None:
        session.add(CharacterPlace(character_id=record.id, location_id=place.id, start=start))
    session.commit()
    return record


def _event(session, place, characters, start, end, name="前の出来事") -> Event:
    record = Event(name=name, text=f"{name}の本文", time=start, start=start, end=end,
                   location_id=place.id)
    record.event_characters = [EventCharacter(character_id=c.id) for c in characters]
    session.add(record)
    session.commit()
    return record


def _involved(session, event) -> set[int]:
    return {row.character_id for row in session.query(EventCharacter).filter_by(event_id=event.id)}


def test_latest_event_is_the_one_that_ends_last_among_the_characters_own(session):
    place = _place(session)
    first = _character(session, place, "甲")
    other = _character(session, place, "乙")
    long_one = _event(session, place, [first], Stamp(2100, 1, 1), Stamp(2100, 3, 1), "長い出来事")
    _event(session, place, [first], Stamp(2100, 1, 10), Stamp(2100, 1, 11), "短い出来事")
    # 甲と同じ id を持つ場所で起きた、甲の関わらない出来事は拾わない
    assert place.id == first.id
    _event(session, place, [other], Stamp(2100, 5, 1), Stamp(2100, 5, 2), "乙の出来事")

    latest = session.scalars(common_query.latest_character_event_select(first.id)).first()

    assert latest.id == long_one.id


def test_next_event_starts_one_to_seven_days_after_the_previous_end(session):
    place = _place(session)
    character = _character(session, place)
    _event(session, place, [character], Stamp(2100, 5, 1), Stamp(2100, 5, 10))

    for seed in range(5):
        previous = session.scalars(common_query.latest_character_event_select(character.id)).first()
        previous_end = previous.end
        record = character_event_generator.generate_next(
            session, MockAIClient(seed=seed), random.Random(seed))

        assert 1 <= days_between(previous_end, record.start) <= 7
        assert record.time == record.start
        assert record.location_id == place.id
        assert character.id in _involved(session, record)


def test_first_event_counts_from_the_first_place_not_the_story(session):
    place = _place(session)
    moved = Location(name="町", kind="町", text="", start=Stamp(2000), active_random_generation=True)
    session.add(moved)
    session.flush()
    character = _character(session, place, start=Stamp(2080))
    session.add(CharacterPlace(character_id=character.id, location_id=moved.id, start=Stamp(2095)))
    session.commit()

    record = character_event_generator.generate_next(session, MockAIClient(seed=1), random.Random(1))

    assert 1 <= days_between(Stamp(2080), record.start) <= 7
    assert record.location_id == place.id


def test_first_event_counts_from_the_birth_when_the_place_has_no_start(session):
    place = _place(session)
    born = Stamp(2105, 6, 1)
    _character(session, place, start=born)
    session.query(CharacterPlace).update({"start": None})
    session.commit()

    record = character_event_generator.generate_next(session, MockAIClient(seed=1), random.Random(1))

    assert 1 <= days_between(born, record.start) <= 7


def test_candidates_are_told_the_drawn_seeds(session):
    place = _place(session)
    _character(session, place)
    ai = MockAIClient(seed=1)
    event_seed.refresh(session, ai)

    character_event_generator.generate_next(session, ai, random.Random(1))

    seeds = [row.text for row in session.query(EventSeed).all()]
    assert seeds
    roll = next(call for call in ai.calls
                if call["schema"] is event_progression_generator._CANDIDATE_SCHEMA)
    assert "出来事の種(時代・場所を抜いた、別の物語から取ったアイデア): [" in roll["prompt"]
    assert any(f"'{seed}'" in roll["prompt"] for seed in seeds)


def test_only_alive_sub_characters_become_the_focus(session):
    place = _place(session)
    _character(session, place, "主役格", main_character=True)
    _character(session, place, "故人", end=Stamp(2080, 1, 1))
    alive = _character(session, place, "生者")

    for seed in range(5):
        record = character_event_generator.generate_next(
            session, MockAIClient(seed=seed), random.Random(seed))
        assert _involved(session, record) == {alive.id}


def test_character_without_a_place_is_passed_over(session):
    place = _place(session)
    _character(session, None, "居場所なし")
    placed = _character(session, place, "居場所あり")

    record = character_event_generator.generate_next(session, MockAIClient(seed=1), _NoShuffle(1))

    assert placed.id in _involved(session, record)


def test_returns_none_when_no_sub_character_can_move(session):
    place = _place(session)
    _character(session, place, main_character=True)

    assert character_event_generator.generate_next(session, MockAIClient(seed=1)) is None


def test_focus_is_involved_even_when_the_ai_leaves_it_out(session):
    place = _place(session)
    character = _character(session, place)

    record = character_event_generator.generate_next(
        session, _LeavesEveryoneOut(seed=1), random.Random(1))

    assert _involved(session, record) == {character.id}


def test_companions_whose_time_is_already_ahead_are_left_out(session):
    place = _place(session)
    focus = _character(session, place, "主役")
    ahead = _character(session, place, "先を行く者")
    behind = _character(session, place, "まだの者")
    _event(session, place, [focus], Stamp(2100, 5, 1), Stamp(2100, 5, 10))
    _event(session, place, [ahead], Stamp(2100, 6, 1), Stamp(2100, 6, 30))
    ai = MockAIClient(seed=1)

    character_event_generator.generate_next(session, ai, _NoShuffle(1))

    prompts = "".join(call["prompt"] for call in ai.calls)
    assert f"'name': '{ahead.name}'" not in prompts
    assert f"'name': '{behind.name}'" in prompts


def test_event_is_decided_by_the_monthly_logic_told_the_focus_and_the_previous_event(session):
    place = _place(session)
    character = _character(session, place)
    _event(session, place, [character], Stamp(2100, 5, 1), Stamp(2100, 5, 10), "峠越え")
    ai = MockAIClient(seed=1)

    character_event_generator.generate_next(session, ai, random.Random(1))

    decide = next(call for call in ai.calls
                  if call["schema"] is event_progression_generator._PLACE_SCHEMA)
    assert decide["system"] == event_progression_generator._PLACE_SYSTEM_PROMPT
    assert (f"この出来事の主役(主役の身に起きる次の出来事として考え、当事者に必ず含める): "
            f"{{'character_id': {character.id}, 'name': '{character.name}'}}") in decide["prompt"]
    assert "'name': '峠越え'" in decide["prompt"]
    assert "'summary': 'モックtext1'" in decide["prompt"]
    assert "峠越えの本文" not in decide["prompt"]


def test_text_is_rewritten_as_a_novel_of_the_decided_event(session):
    place = _place(session)
    character = _character(session, place)
    character.first_person = "僕"
    session.commit()
    _event(session, place, [character], Stamp(2100, 5, 1), Stamp(2100, 5, 10), "峠越え")
    ai = MockAIClient(seed=1)

    record = character_event_generator.generate_next(session, ai, random.Random(1))

    novel = ai.calls[-1]
    assert novel["schema"] is character_event_generator._NOVEL_SCHEMA
    assert EVENT_NOVEL_INSTRUCTION in novel["system"]
    assert EVENT_RECORD_INSTRUCTION not in novel["system"]
    assert '"first_person": "僕"' in novel["prompt"]
    assert '"place": "村"' in novel["prompt"] and '"summary": "モックtext1"' in novel["prompt"]
    assert "峠越えの本文" not in novel["prompt"]
    assert "1700〜2700字の小説" in novel["prompt"]
    assert record.text == f"モックtext{len(ai.calls)}"


class _WritesNoNovel(MockAIClient):
    def try_generate_json(self, prompt, schema, **kwargs):
        if schema is character_event_generator._NOVEL_SCHEMA:
            return {}
        return super().try_generate_json(prompt, schema, **kwargs)


def test_record_text_is_kept_when_the_novel_is_not_written(session):
    place = _place(session)
    _character(session, place)

    record = character_event_generator.generate_next(session, _WritesNoNovel(seed=1), random.Random(1))

    assert record.text.startswith("モックevent_text")


def test_previous_event_is_summarized_first_and_kept(session):
    place = _place(session)
    character = _character(session, place)
    previous = _event(session, place, [character], Stamp(2100, 5, 1), Stamp(2100, 5, 10), "峠越え")
    ai = MockAIClient(seed=1)

    character_event_generator.generate_next(session, ai, random.Random(1))

    summarize = ai.calls[0]
    assert summarize["schema"] is event_summary._SCHEMA
    assert "峠越えの本文" in summarize["prompt"]
    row = session.query(EventSummary).filter_by(event_id=previous.id).one()
    assert row.text == "モックtext1"
    assert row.source_hash == summary_source_hash("峠越えの本文")


def test_summary_is_reused_while_the_text_is_unchanged(session):
    place = _place(session)
    character = _character(session, place)
    previous = _event(session, place, [character], Stamp(2100, 5, 1), Stamp(2100, 5, 10), "峠越え")
    session.add(EventSummary(event_id=previous.id, source_hash=summary_source_hash("峠越えの本文"),
                             text="峠を越えた"))
    session.commit()
    ai = MockAIClient(seed=1)

    character_event_generator.generate_next(session, ai, random.Random(1))

    assert all(call["schema"] is not event_summary._SCHEMA for call in ai.calls)
    assert "'summary': '峠を越えた'" in ai.calls[0]["prompt"]


def test_summary_is_rewritten_when_the_text_changes(session):
    place = _place(session)
    character = _character(session, place)
    previous = _event(session, place, [character], Stamp(2100, 5, 1), Stamp(2100, 5, 10), "峠越え")
    session.add(EventSummary(event_id=previous.id, source_hash=summary_source_hash("古い本文"),
                             text="古い要約"))
    session.commit()
    ai = MockAIClient(seed=1)

    character_event_generator.generate_next(session, ai, random.Random(1))

    assert ai.calls[0]["schema"] is event_summary._SCHEMA
    row = session.query(EventSummary).filter_by(event_id=previous.id).one()
    assert row.text == "モックtext1"
    assert row.source_hash == summary_source_hash("峠越えの本文")


class _WritesNoSummary(MockAIClient):
    def try_generate_json(self, prompt, schema, **kwargs):
        if schema is event_summary._SCHEMA:
            self.calls.append({"prompt": prompt, "system": kwargs.get("system"), "schema": schema})
            return {}
        return super().try_generate_json(prompt, schema, **kwargs)


def test_previous_text_is_passed_when_the_summary_is_not_written(session):
    place = _place(session)
    character = _character(session, place)
    _event(session, place, [character], Stamp(2100, 5, 1), Stamp(2100, 5, 10), "峠越え")
    ai = _WritesNoSummary(seed=1)

    character_event_generator.generate_next(session, ai, random.Random(1))

    assert "'text': '峠越えの本文'" in ai.calls[1]["prompt"]
    assert session.query(EventSummary).count() == 0


def test_monthly_progression_keeps_writing_records():
    system = event_progression_generator._PLACE_SYSTEM_PROMPT
    assert EVENT_RECORD_INSTRUCTION in system
    assert EVENT_NOVEL_INSTRUCTION not in system


def test_daily_event_returns_the_id_of_the_new_event(session):
    place = _place(session)
    character = _character(session, place)

    event_id = main.daily_event(MockAIClient(seed=1))

    record = session.get(Event, event_id)
    assert record is not None
    assert character.id in _involved(session, record)
    # 先に、作品「村の話」の筋書きから種を抜き出している
    assert session.query(EventSeed).count() > 0


def test_first_character_place_is_the_oldest(session):
    place = _place(session)
    moved = Location(name="町", kind="町", text="", start=Stamp(2000))
    session.add(moved)
    session.flush()
    character = _character(session, place, start=Stamp(2080))
    session.add(CharacterPlace(character_id=character.id, location_id=moved.id, start=Stamp(2095)))
    session.commit()

    row = session.scalars(common_query.first_character_place_select(character.id)).first()

    assert row.location_id == place.id
