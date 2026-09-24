"""作品(`Story`)の確定と、話(`Episode`)の md 名 `{story_id}_{number}_{title}.md`。"""
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


def test_episode_markdown_name_puts_story_id_and_number_first():
    assert Episode(id=7, story_id=1, number=3, title="白い灯り", text="").markdown_name == "1_3_白い灯り.md"
    assert Episode(id=8, story_id=1, number=4, text="").markdown_name == "1_4.md"
    # 題だけを使う。filename は見ない
    assert Episode(id=9, story_id=2, number=5, title="題", text="", filename="別名").markdown_name == "2_5_題.md"
    assert Episode(id=10, story_id=2, title="題", text="").markdown_name == "2_題.md"


def test_episode_parse_markdown_stem():
    assert Episode.parse_markdown_stem("1_3_白い灯り") == (None, {"story_id": 1, "number": 3, "title": "白い灯り"})
    assert Episode.parse_markdown_stem("1_4") == (None, {"story_id": 1, "number": 4, "title": None})
    assert Episode.parse_markdown_stem("2_題") == (None, {"story_id": 2, "title": "題"})
    # 手で作った、数の付かない名前は story_id も決まらない
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
    assert episode.filename is None


def test_episode_round_trips_when_number_differs_from_id(session, place, tmp_path):
    story = CommitStory({"name": "遥かなる幻想郷まで", "place_id": place}).run()
    CommitEpisode({"story_id": story["id"], "number": 1, "title": "白い灯り", "text": "一話"}).run()
    second = CommitEpisode({"story_id": story["id"], "number": 7, "title": "裁定", "text": "七話"}).run()

    root = str(tmp_path / "worlds")
    export_db(root)
    assert sorted(os.listdir(os.path.join(root, "episode"))) == ["1_1_白い灯り.md", "1_7_裁定.md"]

    import_db(root)
    session.expire_all()
    assert session.query(Episode).count() == 2
    episode = session.get(Episode, second["id"])
    assert (episode.story_id, episode.number, episode.title) == (1, 7, "裁定")


def test_commit_episode_accepts_key_only(place):
    story = CommitStory({"name": "遥かなる幻想郷まで", "place_id": place}).run()
    episode = CommitEpisode({"story_id": story["id"], "number": 1, "title": "白い灯り",
                             "key": "人工母体から娘が生まれる", "start": "11572/03/25 00:00:00",
                             "viewpoint": "カシル", "place": "エンピレオ 血統管理省"}).run()
    assert episode["key"] == "人工母体から娘が生まれる"
    assert (episode["text"], episode["letters"]) == ("", 0)
    assert (episode["viewpoint"], episode["place"]) == ("カシル", "エンピレオ 血統管理省")
    assert str(episode["start"]) == "11572/03/25 00:00:00"


def test_commit_episode_requires_key_or_text(place):
    story = CommitStory({"name": "遥かなる幻想郷まで", "place_id": place}).run()
    with pytest.raises(ValueError):
        CommitEpisode({"story_id": story["id"], "number": 1, "title": "白い灯り"}).run()


def test_episode_markdown_has_data_key_text_sections(session, place, tmp_path):
    story = CommitStory({"name": "遥かなる幻想郷まで", "place_id": place}).run()
    CommitEpisode({"story_id": story["id"], "number": 1, "title": "白い灯り",
                   "key": "## 出来事\n娘が生まれる", "text": "本文", "viewpoint": "カシル",
                   "place": "エンピレオ", "start": "11572/03/25 00:00:00"}).run()

    root = str(tmp_path / "worlds")
    export_db(root)
    with open(os.path.join(root, "episode", "1_1_白い灯り.md"), encoding="utf-8") as f:
        content = f.read()
    assert "# data\n" in content
    assert content.index("# key\n") < content.index("# text\n")
    assert "## 出来事\n娘が生まれる" in content
    # 節として出す列は `# data` に出さない
    assert '"key"' not in content and '"text"' not in content
    assert '"viewpoint": "カシル"' in content

    import_db(root)
    session.expire_all()
    episode = session.get(Episode, 1)
    assert (episode.key, episode.text) == ("## 出来事\n娘が生まれる", "本文")
    assert (episode.viewpoint, episode.place) == ("カシル", "エンピレオ")
    assert str(episode.start) == "11572/03/25 00:00:00"


def test_episode_markdown_keeps_empty_sections(session, place, tmp_path):
    story = CommitStory({"name": "遥かなる幻想郷まで", "place_id": place}).run()
    CommitEpisode({"story_id": story["id"], "number": 1, "title": "白い灯り",
                   "key": "種だけ"}).run()

    root = str(tmp_path / "worlds")
    export_db(root)
    import_db(root)
    session.expire_all()
    episode = session.get(Episode, 1)
    assert (episode.key, episode.text) == ("種だけ", "")


def test_story_markdown_name_keeps_filename(session, place, tmp_path):
    CommitStory({"name": "遥かなる幻想郷まで", "place_id": place,
                 "filename": "遥かなる幻想郷まで"}).run()
    root = str(tmp_path / "worlds")
    export_db(root)
    assert os.listdir(os.path.join(root, "story")) == ["1_遥かなる幻想郷まで.md"]

    import_db(root)
    session.expire_all()
    assert session.get(Story, 1).filename == "遥かなる幻想郷まで"
