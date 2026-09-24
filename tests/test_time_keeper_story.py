import pytest

from ai.time_keeper import main
from ai.time_keeper._format import add_years, days_between
from db.schema import Location, Story
from db.stamp import Stamp
from tool.test.mock_ai_client import MockAIClient


def test_add_years_keeps_month_and_day():
    assert add_years(Stamp(2100, 3, 4, 5, 6, 7), 5) == Stamp(2105, 3, 4, 5, 6, 7)


def test_days_between_matches_add_days_roundtrip():
    start = Stamp(2100, 1, 1)
    end = add_years(start, 5)
    days = days_between(start, end)
    assert days == 5 * 365 + 1  # 2100-2104 に閏年が一つ(2104)入る


def test_loop_time_for_story_starts_at_story_start_and_covers_years(session, monkeypatch):
    place = Location(name="村", kind="村", text="")
    session.add(place)
    session.flush()
    story = Story(name="村の話", place_id=place.id, text="筋書き", narration="", state="構想中",
                  start=Stamp(2100, 4, 1), end=Stamp(2300))
    session.add(story)
    session.commit()

    captured = {}

    def fake_loop_time(ai, start_time, max_days):
        captured["ai"] = ai
        captured["start_time"] = start_time
        captured["max_days"] = max_days
        return start_time

    monkeypatch.setattr(main, "loop_time", fake_loop_time)
    ai = MockAIClient()

    result = main.loop_time_for_story(ai, story.id, years=5)

    assert captured["ai"] is ai
    assert captured["start_time"] == Stamp(2100, 4, 1)
    assert captured["max_days"] == days_between(Stamp(2100, 4, 1), Stamp(2105, 4, 1))
    assert result == Stamp(2100, 4, 1)


def test_loop_time_for_story_rejects_missing_story(session):
    with pytest.raises(ValueError, match="見つからない"):
        main.loop_time_for_story(MockAIClient(), 999)


def test_loop_time_for_story_rejects_story_without_start(session):
    place = Location(name="村", kind="村", text="")
    session.add(place)
    session.flush()
    story = Story(name="村の話", place_id=place.id, text="筋書き", narration="", state="構想中")
    session.add(story)
    session.commit()

    with pytest.raises(ValueError, match="start が無い"):
        main.loop_time_for_story(MockAIClient(), story.id)
