"""出来事の種(`event_seed`)。作品・話・人物の筋書き・出来事から抜き出して貯め、ランダムに引く。"""
import random

from DEM.ai.time_keeper import event_seed
from DEM.data_access_logic.query import event_seed_query
from DEM.db.schema import Character, Episode, Event, EventSeed, EventSeedSource, Story
from DEM.db.stamp import Stamp
from DEM.tool.test.mock_ai_client import MockAIClient


class _Fails(MockAIClient):
    def try_generate_json(self, prompt, schema, **kwargs):
        super().try_generate_json(prompt, schema, **kwargs)
        return {}


class _NoSeeds(MockAIClient):
    def try_generate_json(self, prompt, schema, **kwargs):
        super().try_generate_json(prompt, schema, **kwargs)
        return {"seeds": []}


def _story(session, text="村の筋書き") -> Story:
    story = Story(name="村の話", text=text, narration="", state="構想中")
    session.add(story)
    session.commit()
    return story


def _sources(session) -> set[tuple[str, int]]:
    return {(column, getattr(row, column)) for row in session.query(EventSeedSource).all()
            for column in ("story_id", "episode_id", "character_id", "event_id")
            if getattr(row, column) is not None}


def test_seeds_are_drawn_out_of_stories_episodes_character_plots_and_events(session):
    story = _story(session)
    with_key = Episode(story_id=story.id, number=1, title="一", text="本文一", key="種一", synced=False)
    text_only = Episode(story_id=story.id, number=2, title="二", text="本文二", key="", synced=False)
    empty = Episode(story_id=story.id, number=3, title="三", text="", key="", synced=False)
    planned = Character(name="甲", text="説明\n\n# plot\n\n起: 旅に出る\n\n# 来歴\n\n村の生まれ")
    unplanned = Character(name="乙", text="説明だけ")
    happened = Event(name="峠越え", text="峠を越えた", time=Stamp(2100))
    session.add_all([with_key, text_only, empty, planned, unplanned, happened])
    session.commit()
    ai = MockAIClient(seed=1)

    added = event_seed.refresh(session, ai)

    assert _sources(session) == {
        ("story_id", story.id), ("episode_id", with_key.id), ("episode_id", text_only.id),
        ("character_id", planned.id), ("event_id", happened.id)}
    assert added == session.query(EventSeed).count() == 2
    prompt = ai.calls[0]["prompt"]
    assert "種一" in prompt and "本文一" not in prompt and "本文二" in prompt
    assert "起: 旅に出る" in prompt and "村の生まれ" not in prompt
    assert "## 元5(event)\n峠を越えた" in prompt
    assert ai.calls[0]["system"] == event_seed._SYSTEM_PROMPT


def test_unseeded_records_are_the_ones_without_a_source_row(session):
    seeded = _story(session, "一つ目")
    unseeded = _story(session, "二つ目")
    session.add(EventSeedSource(story_id=seeded.id, source_hash="x"))
    session.add(EventSeedSource(event_id=seeded.id, source_hash="x"))
    session.commit()

    rows = session.scalars(event_seed_query.unseeded_select(Story)).all()

    assert [row.id for row in rows] == [unseeded.id]


def test_unchanged_sources_are_not_drawn_again_even_without_seeds(session):
    _story(session)
    event_seed.refresh(session, _NoSeeds(seed=1))
    ai = MockAIClient(seed=1)

    assert event_seed.refresh(session, ai) == 0
    assert ai.calls == []


def test_only_the_changed_source_is_drawn_again(session):
    changed = _story(session, "一つ目")
    kept = _story(session, "二つ目")
    event_seed.refresh(session, MockAIClient(seed=1))
    kept_seeds = {row.id for row in session.query(EventSeed).join(EventSeedSource)
                  .filter(EventSeedSource.story_id == kept.id)}
    changed.text = "一つ目を書き直した"
    session.commit()
    ai = MockAIClient(seed=2)

    event_seed.refresh(session, ai)

    assert len(ai.calls) == 1
    assert "一つ目を書き直した" in ai.calls[0]["prompt"] and "二つ目" not in ai.calls[0]["prompt"]
    assert kept_seeds <= {row.id for row in session.query(EventSeed).all()}


def test_seeds_of_a_removed_source_are_dropped(session):
    story = _story(session)
    event_seed.refresh(session, MockAIClient(seed=1))
    assert session.query(EventSeed).count() > 0
    story.text = ""
    session.commit()

    event_seed.refresh(session, MockAIClient(seed=1))

    assert _sources(session) == set()
    assert session.query(EventSeed).count() == 0


def test_sources_are_drawn_again_when_the_ai_fails(session):
    _story(session)
    event_seed.refresh(session, _Fails(seed=1))
    assert _sources(session) == set()
    ai = MockAIClient(seed=1)

    event_seed.refresh(session, ai)

    assert len(ai.calls) == 1
    assert len(_sources(session)) == 1


def test_sources_are_split_by_letters(session, monkeypatch):
    monkeypatch.setattr(event_seed.constants, "EVENT_SEED_BATCH_LETTERS", 10)
    for text in ("あ" * 6, "い" * 6, "う" * 3):
        _story(session, text)
    ai = MockAIClient(seed=1)

    event_seed.refresh(session, ai)

    assert len(ai.calls) == 2
    assert "い" * 6 in ai.calls[1]["prompt"] and "う" * 3 in ai.calls[1]["prompt"]


def test_draw_picks_distinct_seeds_at_random(session):
    story = _story(session)
    source = EventSeedSource(story_id=story.id, source_hash="x")
    session.add(source)
    session.flush()
    session.add_all([EventSeed(event_seed_source_id=source.id, text=f"種{i}") for i in range(5)])
    session.commit()

    drawn = event_seed.draw(session, random.Random(1), 3)

    assert len(drawn) == len(set(drawn)) == 3
    assert len(event_seed.draw(session, random.Random(1), 10)) == 5


def test_draw_from_an_empty_pool_is_empty(session):
    assert event_seed.draw(session, random.Random(1)) == []


def test_seeds_of_a_deleted_record_are_dropped(session):
    happened = Event(name="峠越え", text="峠を越えた", time=Stamp(2100))
    session.add(happened)
    session.commit()
    event_seed.refresh(session, MockAIClient(seed=1))
    session.delete(happened)
    session.commit()

    event_seed.refresh(session, MockAIClient(seed=1))

    assert _sources(session) == set()
    assert session.query(EventSeed).count() == 0


def test_a_note_appended_outside_the_plot_does_not_draw_the_character_again(session):
    character = Character(name="甲", text="説明\n\n# plot\n\n起: 旅に出る")
    session.add(character)
    session.commit()
    event_seed.refresh(session, MockAIClient(seed=1))
    character.text = "説明に追記\n\n# plot\n\n起: 旅に出る"
    session.commit()
    ai = MockAIClient(seed=1)

    event_seed.refresh(session, ai)

    assert ai.calls == []
