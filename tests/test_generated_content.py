"""ミームの棚卸しと要約(`event_summary` / `episode_summary`)をまとめて作る `generated_content.refresh`。

出来事・話を確定したときに毎回呼ぶ、パックにした処理。
"""
from DEM.ai.time_keeper import generated_content
from DEM.db.schema import Episode, Event, EventSummary, EpisodeSummary, Idea, Location, Story
from DEM.db.stamp import Stamp
from DEM.tool.test.mock_ai_client import MockAIClient


def test_refresh_without_a_record_only_tends_to_memes(session):
    idea = Idea(name="語", kind="用語", text="語の説明")
    session.add(idea)
    session.commit()
    ai = MockAIClient(seed=1)

    result = generated_content.refresh(session, ai)

    assert result == {"memes_added": 0, "summarized": False}
    assert idea.meme_seeded


def test_refresh_summarizes_the_given_event(session):
    event = Event(name="出来事", text="本文", time=Stamp(2100))
    session.add(event)
    session.commit()
    ai = MockAIClient(seed=1)

    result = generated_content.refresh(session, ai, event)

    assert result["summarized"] is True
    assert session.query(EventSummary).filter_by(event_id=event.id).count() == 1


def test_refresh_summarizes_the_given_episode(session):
    place = Location(name="村", kind="村", text="")
    session.add(place)
    session.flush()
    story = Story(name="作品", place_id=place.id, text="", narration="", state="")
    session.add(story)
    session.flush()
    episode = Episode(story_id=story.id, number=1, title="第一話", text="本文", letters=2)
    session.add(episode)
    session.commit()
    ai = MockAIClient(seed=1)

    result = generated_content.refresh(session, ai, episode)

    assert result["summarized"] is True
    assert session.query(EpisodeSummary).filter_by(episode_id=episode.id).count() == 1


def test_refresh_skips_summary_for_a_record_without_text(session):
    event = Event(name="出来事", text="", time=Stamp(2100))
    session.add(event)
    session.commit()
    ai = MockAIClient(seed=1)

    result = generated_content.refresh(session, ai, event)

    assert result["summarized"] is False
    assert session.query(EventSummary).count() == 0
