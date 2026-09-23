"""作品(`Story`)の確定と、話(`Episode`)の md 名 `{story_id}_{id}_{title}.md`。"""
import os

import pytest

from DEM.ai.claude_code.interface._base import UnknownRecordError
from DEM.ai.claude_code.interface.story.commit_episode import CommitEpisode
from DEM.ai.claude_code.interface.story.commit_story import CommitStory
from DEM.db.schema import Episode, Location, Story
from DEM.tool.markdown.export_db import export_db
from DEM.tool.markdown.import_db import import_db


@pytest.fixture
def place(session):
    location = Location(name="ノウル", kind="星", text="")
    session.add(location)
    session.commit()
    return location.id


def test_commit_story_returns_row(place):
    story = CommitStory({"name": "遥かなる幻想郷まで", "place_id": place,
                         "narration": "三人称", "state": "構想中",
                         "start": "11572/03/24 00:00:00", "text": "本編"}).run()
    assert story["name"] == "遥かなる幻想郷まで"
    assert story["place_id"] == place
    assert str(story["start"]) == "11572/03/24 00:00:00"


def test_commit_story_requires_name(place):
    with pytest.raises(ValueError):
        CommitStory({"place_id": place}).run()


def test_commit_story_rejects_unknown_place():
    with pytest.raises(UnknownRecordError):
        CommitStory({"name": "作品", "place_id": 9999}).run()


def test_episode_markdown_name_puts_story_id_first():
    assert Episode(id=7, story_id=1, title="白い灯り", text="").markdown_name == "1_7_白い灯り.md"
    assert Episode(id=8, story_id=1, text="").markdown_name == "1_8.md"
    assert Episode(id=9, story_id=2, title="題", text="", filename="別名").markdown_name == "2_9_別名.md"


def test_episode_parse_markdown_stem():
    assert Episode.parse_markdown_stem("1_7_白い灯り") == (7, {"story_id": 1, "filename": "白い灯り"})
    assert Episode.parse_markdown_stem("1_8") == (8, {"story_id": 1, "filename": None})
    # 手で作った、数の付かない名前は id も story_id も決まらない
    assert Episode.parse_markdown_stem("下書き") == (None, {"filename": "下書き"})


def test_episode_round_trips_through_markdown(session, place, tmp_path):
    story = CommitStory({"name": "遥かなる幻想郷まで", "place_id": place}).run()
    CommitEpisode({"story_id": story["id"], "number": 1,
                   "title": "白い灯り", "text": "骨組み"}).run()

    root = str(tmp_path / "worlds")
    export_db(root)
    assert os.listdir(os.path.join(root, "episode")) == ["1_1_白い灯り.md"]

    import_db(root)
    session.expire_all()
    assert session.query(Episode).count() == 1
    episode = session.get(Episode, 1)
    assert (episode.story_id, episode.number, episode.title) == (1, 1, "白い灯り")
    # 題から自動で付く部分なので filename には残らない
    assert episode.filename is None


def test_story_markdown_name_keeps_filename(session, place, tmp_path):
    CommitStory({"name": "遥かなる幻想郷まで", "place_id": place,
                 "filename": "遥かなる幻想郷まで"}).run()
    root = str(tmp_path / "worlds")
    export_db(root)
    assert os.listdir(os.path.join(root, "story")) == ["1_遥かなる幻想郷まで.md"]

    import_db(root)
    session.expire_all()
    assert session.get(Story, 1).filename == "遥かなる幻想郷まで"
