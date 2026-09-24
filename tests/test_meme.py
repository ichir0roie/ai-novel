"""ミーム(`meme`)。アイデア(idea)・oracle・人物の筋書きから抜き出して貯める。

抜き出しは元のレコードごとに一度だけで、元の `meme_seeded` で管理する。
"""
from DEM.ai.time_keeper import meme
from DEM.data_access_logic.query import meme_query
from DEM.db.schema import Character, Idea, Meme, Oracle
from DEM.tool.test.mock_ai_client import MockAIClient


class _Fails(MockAIClient):
    def try_generate_json(self, prompt, schema, **kwargs):
        super().try_generate_json(prompt, schema, **kwargs)
        return {}


class _NoMemes(MockAIClient):
    def try_generate_json(self, prompt, schema, **kwargs):
        super().try_generate_json(prompt, schema, **kwargs)
        return {"memes": []}


def _idea(session, text="語の説明") -> Idea:
    idea = Idea(name="語", kind="用語", text=text)
    session.add(idea)
    session.commit()
    return idea


def _oracle(session, text="覚え書き") -> Oracle:
    oracle = Oracle(text=text)
    session.add(oracle)
    session.commit()
    return oracle


def test_memes_are_drawn_out_of_ideas_oracles_and_character_plots(session):
    idea = _idea(session)
    oracle = _oracle(session)
    planned = Character(name="甲", text="説明\n\n# plot\n\n起: 旅に出る\n\n# 来歴\n\n村の生まれ")
    unplanned = Character(name="乙", text="説明だけ")
    session.add_all([planned, unplanned])
    session.commit()
    ai = MockAIClient(seed=1)

    added = meme.refresh(session, ai)

    assert added == session.query(Meme).count()
    assert all(record.meme_seeded for record in (idea, oracle, planned))
    # 筋書きの節が無い人物は、書かれるまで印を立てない
    assert not unplanned.meme_seeded
    prompt = ai.calls[0]["prompt"]
    assert "語の説明" in prompt and "覚え書き" in prompt
    assert "起: 旅に出る" in prompt and "村の生まれ" not in prompt
    assert ai.calls[0]["system"] == meme._SYSTEM_PROMPT


def test_unseeded_records_are_the_ones_not_flagged(session):
    seeded = _idea(session, "一つ目")
    unseeded = _idea(session, "二つ目")
    seeded.meme_seeded = True
    session.commit()

    rows = session.scalars(meme_query.unseeded_select(Idea)).all()

    assert [row.id for row in rows] == [unseeded.id]


def test_a_source_is_drawn_only_once_even_without_memes_or_after_edits(session):
    idea = _idea(session)
    meme.refresh(session, _NoMemes(seed=1))
    idea.text = "書き直した説明"
    session.commit()
    ai = MockAIClient(seed=1)

    assert meme.refresh(session, ai) == 0
    assert ai.calls == []


def test_clearing_the_flag_draws_the_source_again(session):
    idea = _idea(session)
    meme.refresh(session, MockAIClient(seed=1))
    idea.text = "書き直した説明"
    idea.meme_seeded = False
    session.commit()
    ai = MockAIClient(seed=2)

    meme.refresh(session, ai)

    assert "書き直した説明" in ai.calls[0]["prompt"]
    assert idea.meme_seeded


def test_sources_are_drawn_again_when_the_ai_fails(session):
    idea = _idea(session)
    meme.refresh(session, _Fails(seed=1))
    assert not idea.meme_seeded
    ai = MockAIClient(seed=1)

    meme.refresh(session, ai)

    assert len(ai.calls) == 1
    assert idea.meme_seeded


def test_sources_are_split_by_letters(session, monkeypatch):
    monkeypatch.setattr(meme.constants, "MEME_BATCH_LETTERS", 10)
    for text in ("あ" * 6, "い" * 6, "う" * 3):
        _idea(session, text)
    ai = MockAIClient(seed=1)

    meme.refresh(session, ai)

    assert len(ai.calls) == 2
    assert "い" * 6 in ai.calls[1]["prompt"] and "う" * 3 in ai.calls[1]["prompt"]
