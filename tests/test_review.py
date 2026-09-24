"""アイデア・ミームを AI にネット検索で検めさせ、妥当性と補足を `review` 欄へ書く。"""
import os

import pytest

from ai.claude_code import ai_client, reviewer
from ai.claude_code.interface.meme import extract_memes
from ai.claude_code.interface.meme.extract_memes import ExtractMemes
from ai.claude_code.interface.randomizer.commit_idea import CommitIdea
from ai.claude_code.interface.review.review_records import ReviewRecords
from db.schema import Idea, Meme
from tool.markdown.export_db import export_db
from tool.markdown.import_db import import_db


class _Reviewer:
    """渡された番号ぶん、`検めた:<本文の先頭行>` を返す。呼び出しの中身を残す。"""

    def __init__(self):
        self.calls = []

    def __call__(self, prompt, schema, **kwargs):
        self.calls.append((prompt, kwargs))
        blocks = prompt.split("\n\n")[:-1]
        return {"reviews": [
            {"number": number, "review": f"## 妥当性\n検めた:{block.splitlines()[-1]}"}
            for number, block in enumerate(blocks, start=1)]}


@pytest.fixture
def fake_review(monkeypatch):
    fake = _Reviewer()
    monkeypatch.setattr(ai_client, "try_generate_json", fake)
    return fake


def test_build_args_allows_given_tools_only():
    plain = ai_client._build_args(None, None)
    assert plain[plain.index("--tools") + 1] == ""
    assert "--allowedTools" not in plain

    searching = ai_client._build_args(None, None, reviewer.REVIEW_TOOLS)
    assert searching[searching.index("--tools") + 1] == "WebSearch,WebFetch"
    assert searching[searching.index("--allowedTools") + 1] == "WebSearch,WebFetch"


def test_review_fills_only_unreviewed_with_text(session, fake_review):
    session.add_all([
        Idea(name="魔力", kind="概念", text="大気に満ちる力"),
        Idea(name="済み", kind="概念", text="検めてある", review="前の結果"),
        Idea(name="空", kind="概念", text=""),
    ])
    session.commit()

    assert ReviewRecords("idea").run() == 1

    session.expire_all()
    rows = {row.name: row.review for row in session.query(Idea).all()}
    assert rows == {"魔力": "## 妥当性\n検めた:大気に満ちる力", "済み": "前の結果", "空": None}
    prompt, kwargs = fake_review.calls[0]
    assert "アイデア「魔力」" in prompt
    assert kwargs["tools"] == reviewer.REVIEW_TOOLS


def test_review_by_ids_redoes_reviewed(session, fake_review):
    meme = Meme(text="約束は守る", category="信条", review="古い結果")
    session.add(meme)
    session.commit()

    assert ReviewRecords("meme", ids=[meme.id]).run() == 1

    session.expire_all()
    assert session.get(Meme, meme.id).review == "## 妥当性\n検めた:約束は守る"


def test_review_keeps_empty_when_ai_fails(session):
    session.add(Meme(text="約束は守る", category="信条"))
    session.commit()

    assert ReviewRecords("meme").run() == 0
    session.expire_all()
    assert session.query(Meme).one().review is None


def test_review_rejects_unknown_table():
    with pytest.raises(ValueError, match="table は"):
        ReviewRecords("event")


def test_commit_idea_reviews_after_commit(session, fake_review):
    result = CommitIdea({"name": "魔力灯り", "kind": "技術", "text": "魔力で灯る明かり"}).run()
    assert result["review"] == "## 妥当性\n検めた:魔力で灯る明かり"

    skipped = CommitIdea({"name": "外部デバイス", "kind": "技術", "text": "身体アシスト"}, review=False).run()
    assert skipped["review"] is None
    assert len(fake_review.calls) == 1


def test_extract_memes_reviews_only_new(session, fake_review, monkeypatch):
    old = Meme(text="古いミーム", category="信条")
    session.add(old)
    session.commit()

    def refresh(s, ai):
        s.add(Meme(text="新しいミーム", category="欲求"))
        s.commit()
        return 1

    monkeypatch.setattr(extract_memes._meme, "refresh", refresh)
    assert ExtractMemes().run() == 1

    session.expire_all()
    reviews = {meme.text: meme.review for meme in session.query(Meme).all()}
    assert reviews == {"古いミーム": None, "新しいミーム": "## 妥当性\n検めた:新しいミーム"}


def test_review_round_trips_through_markdown(session, tmp_path):
    session.add(Idea(id=5, name="魔力", kind="概念", text="本文", review="## 妥当性\nありえる"))
    session.commit()
    root = str(tmp_path / "worlds")

    export_db(root)
    with open(os.path.join(root, "idea", "5_魔力.md"), encoding="utf-8") as f:
        assert "# review\n## 妥当性\nありえる\n" in f.read()

    session.get(Idea, 5).review = None
    session.commit()
    import_db(root)

    session.expire_all()
    idea = session.get(Idea, 5)
    assert idea.text == "本文" and idea.review == "## 妥当性\nありえる"
