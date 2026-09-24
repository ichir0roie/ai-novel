"""本文を書く前に直前の話から作る覚え書き(概要と文体)と、それを載せた本文のプロンプト。"""
import pytest

from DEM.ai.claude_code import story_writer
from DEM.db.schema import Episode, Location, Story, StorySummary, summary_source_hash
from DEM.db.stamp import Stamp


@pytest.fixture
def story(session):
    place = Location(name="村", kind="村", text="")
    session.add(place)
    session.flush()
    record = Story(name="村の話", place_id=place.id, text="筋書き", narration="三人称",
                   state="執筆中", start=Stamp(2100, 4, 1), end=Stamp(2300))
    session.add(record)
    session.commit()
    return record


def add_episodes(session, story, count):
    for number in range(1, count + 1):
        session.add(Episode(story_id=story.id, number=number, title=f"第{number}話",
                            text=f"{number}話の本文", letters=6, synced=True))
    session.commit()


@pytest.fixture
def calls(monkeypatch):
    """`try_generate_json` の呼び出しを順に記録し、schema で返す中身を選ぶ。"""
    recorded = []

    def fake(prompt, schema, *, system=None, timeout=None, options=None):
        recorded.append({"prompt": prompt, "schema": schema, "system": system})
        if schema is story_writer._RECAP_SCHEMA:
            return {"summary": "二人が村を出た", "style": "短い地の文と会話"}
        return {"title": "題", "text": "本文"}

    monkeypatch.setattr(story_writer.ai_client, "try_generate_json", fake)
    return recorded


def test_recap_reads_only_the_last_two_episodes_one_by_one(session, story, calls):
    add_episodes(session, story, 3)

    story_writer.write_next_episode(session, story.id)

    recaps = [call for call in calls if call["schema"] is story_writer._RECAP_SCHEMA]
    assert len(recaps) == 2
    assert "2話の本文" in recaps[0]["prompt"] and "3話の本文" not in recaps[0]["prompt"]
    assert "3話の本文" in recaps[1]["prompt"]
    assert all("1話の本文" not in call["prompt"] for call in recaps)


def test_episode_prompt_carries_the_recap(session, story, calls):
    add_episodes(session, story, 2)

    record = story_writer.write_next_episode(session, story.id)

    episode_prompt = calls[-1]["prompt"]
    assert "直前の話の概要: 第1話: 二人が村を出た\n第2話: 二人が村を出た" in episode_prompt
    assert "直前の話の文体(これに揃える): 短い地の文と会話" in episode_prompt
    assert record.number == 3


def test_recap_is_kept_in_the_story_summary_table(session, story, calls):
    add_episodes(session, story, 2)

    story_writer.write_next_episode(session, story.id)

    rows = session.query(StorySummary).order_by(StorySummary.episode_id).all()
    assert [(row.story_id, row.summary, row.style) for row in rows] == [
        (story.id, "二人が村を出た", "短い地の文と会話")] * 2
    assert rows[0].source_hash == summary_source_hash("1話の本文")


def test_recap_is_reused_while_the_episode_text_is_unchanged(session, story, calls):
    add_episodes(session, story, 2)
    story_writer.write_next_episode(session, story.id)
    calls.clear()

    story_writer.write_next_episode(session, story.id)

    recaps = [call for call in calls if call["schema"] is story_writer._RECAP_SCHEMA]
    assert len(recaps) == 1
    assert "本文" in recaps[0]["prompt"] and "2話の本文" not in recaps[0]["prompt"]


def test_recap_is_rewritten_when_the_episode_text_changes(session, story, calls):
    add_episodes(session, story, 2)
    story_writer.write_next_episode(session, story.id, number=3)
    episode = session.query(Episode).filter_by(story_id=story.id, number=2).one()
    episode.text = "2話の書き直した本文"
    session.commit()
    calls.clear()

    story_writer.write_next_episode(session, story.id, number=3)

    recaps = [call for call in calls if call["schema"] is story_writer._RECAP_SCHEMA]
    assert len(recaps) == 1 and "2話の書き直した本文" in recaps[0]["prompt"]
    row = session.query(StorySummary).filter_by(episode_id=episode.id).one()
    assert row.source_hash == summary_source_hash("2話の書き直した本文")


def test_first_episode_skips_the_recap(session, story, calls):
    record = story_writer.write_next_episode(session, story.id)

    assert len(calls) == 1
    assert calls[0]["schema"] is story_writer._SCHEMA
    assert record.number == 1


def test_episode_is_written_without_a_usable_recap(session, story, monkeypatch):
    add_episodes(session, story, 2)
    prompts = []

    def fake(prompt, schema, *, system=None, timeout=None, options=None):
        prompts.append(prompt)
        if schema is story_writer._RECAP_SCHEMA:
            return {}
        return {"title": "題", "text": "本文"}

    monkeypatch.setattr(story_writer.ai_client, "try_generate_json", fake)

    record = story_writer.write_next_episode(session, story.id)

    assert "直前の話の概要" not in prompts[-1]
    assert "直前の話の文体" not in prompts[-1]
    assert session.query(StorySummary).count() == 0
    assert record.text == "本文"


def test_system_prompt_tells_to_follow_the_recap():
    assert "概要の筋をそのまま受け継ぎ" in story_writer._SYSTEM_PROMPT


def test_seeded_episode_is_filled_in_place(session, story, calls):
    add_episodes(session, story, 2)
    session.add(Episode(story_id=story.id, number=3, title="堕ちる翼",
                        key="## 場面\n1. 面会室 / ミレア", text="", letters=0,
                        viewpoint="ミレア", place="エンピレオ", synced=False))
    session.commit()

    record = story_writer.write_next_episode(session, story.id)

    assert record.number == 3
    assert record.text == "本文"
    assert record.key == "## 場面\n1. 面会室 / ミレア"
    prompt = calls[-1]["prompt"]
    assert "この話の種" in prompt and "面会室 / ミレア" in prompt
    assert "視点と場所: ミレア / エンピレオ" in prompt


def test_number_picks_the_episode_to_write(session, story, calls):
    add_episodes(session, story, 1)
    for number in (2, 3):
        session.add(Episode(story_id=story.id, number=number, title="", key=f"種{number}",
                            text="", letters=0, synced=False))
    session.commit()

    record = story_writer.write_next_episode(session, story.id, number=3)

    assert record.number == 3
    assert "種3" in calls[-1]["prompt"]


def test_seeded_later_episodes_do_not_block_writing(session, story, calls):
    add_episodes(session, story, 1)
    session.add(Episode(story_id=story.id, number=9, title="", key="先の種",
                        text="", letters=0, synced=False))
    session.commit()

    assert story_writer.write_next_episode(session, story.id) is not None


def test_unsynced_written_episode_blocks_writing(session, story, calls):
    add_episodes(session, story, 2)
    session.add(Episode(story_id=story.id, number=3, title="", key="", text="書いた本文",
                        letters=5, synced=False))
    session.commit()

    assert story_writer.write_next_episode(session, story.id, number=4) is None


def test_previous_episodes_are_taken_from_before_the_target(session, story, calls):
    add_episodes(session, story, 2)
    session.add(Episode(story_id=story.id, number=7, title="先の話", key="",
                        text="7話の本文", letters=6, synced=True))
    session.commit()

    story_writer.write_next_episode(session, story.id, number=3)

    assert "7話の本文" not in calls[0]["prompt"]


def test_system_prompt_states_the_length_target():
    assert "一話は5000〜8000字" in story_writer._SYSTEM_PROMPT
    assert "場面" in story_writer._SYSTEM_PROMPT
