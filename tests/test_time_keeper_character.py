import random

from ai.time_keeper import constants
from ai.time_keeper.random_character_generator import (
    _CONTENT_SYSTEM_PROMPT, _NON_PERSON_CONTENT_SYSTEM_PROMPT, _generate_one, _personality_label,
    history_section,
)
from db.schema import (
    MEME_CATEGORIES, PERSONALITY_COLUMNS, PERSONALITY_LEVELS, Character, Location, Meme, Story,
)
from db.stamp import Stamp
from tool.test.mock_ai_client import MockAIClient

_ALL_HIGH = {name: "高" for name in PERSONALITY_COLUMNS}


def test_personality_label_uses_column_comments():
    label = _personality_label(dict(_ALL_HIGH, sincerity="無", imagination="必"))
    parts = label.split(" / ")
    assert len(parts) == 12
    assert parts[0] == "誠実性=無"
    assert parts[-1] == "想像力=必"
    assert all(part.endswith("=高") for part in parts[1:-1])


def test_personality_label_accepts_record():
    record = Character(name="x", text="", **_ALL_HIGH)
    assert _personality_label(record) == _personality_label(_ALL_HIGH)


def test_system_prompt_explains_levels():
    assert "/".join(PERSONALITY_LEVELS) in _CONTENT_SYSTEM_PROMPT
    assert "サイコロで決まっていて変えられない" in _CONTENT_SYSTEM_PROMPT


def _place(session) -> Location:
    place = Location(name="村", kind="村", text="山あいの村", start=Stamp(2000))
    session.add(place)
    session.flush()
    session.add(Story(name="村の話", place_id=place.id, text="村の筋書き", narration="", state="構想中",
                      start=Stamp(2000), end=Stamp(2300)))
    session.commit()
    return place


def test_generate_person_passes_personality_to_ai_and_keeps_it(session):
    place = _place(session)
    ai = MockAIClient(seed=1)

    record = _generate_one(session, place, Stamp(2100, 1, 1), random.Random(1), ai, person=True)

    levels = {name: getattr(record, name) for name in PERSONALITY_COLUMNS}
    assert all(value in PERSONALITY_LEVELS for value in levels.values())

    content_call = next(c for c in ai.calls if c["system"] == _CONTENT_SYSTEM_PROMPT)
    expected_line = f"性格({'/'.join(PERSONALITY_LEVELS)} の五段階): {_personality_label(levels)}"
    assert expected_line in content_call["prompt"]
    # 命名も、決まった性格を材料にする
    name_call = ai.calls[-1]
    assert _personality_label(levels) in name_call["prompt"]

    session.expire_all()
    stored = session.get(Character, record.id)
    assert {name: getattr(stored, name) for name in PERSONALITY_COLUMNS} == levels


def test_generate_non_person_has_no_personality_line(session):
    place = _place(session)
    ai = MockAIClient(seed=2)

    record = _generate_one(session, place, Stamp(2100, 1, 1), random.Random(2), ai, person=False)

    assert record.kind != "人物"
    assert record.sex is None and record.tone is None
    assert all("性格(" not in c["prompt"] for c in ai.calls)


def _one_meme_per_category(session, monkeypatch):
    session.add_all([Meme(text=f"{category}のミーム", category=category) for category in MEME_CATEGORIES])
    session.commit()
    monkeypatch.setattr(constants, "MEME_DRAW_RANGE", (1, 1))


def test_generate_person_passes_drawn_memes_and_writes_them_into_text(session, monkeypatch):
    place = _place(session)
    _one_meme_per_category(session, monkeypatch)
    ai = MockAIClient(seed=1)

    record = _generate_one(session, place, Stamp(2100, 1, 1), random.Random(1), ai, person=True)

    prompt = next(c for c in ai.calls if c["system"] == _CONTENT_SYSTEM_PROMPT)["prompt"]
    assert "この人物の行動原理(ミーム。古=" in prompt
    section = record.text.split("# meme\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert sorted(line.split(": ", 1)[1] for line in section) == sorted(
        f"{category}のミーム" for category in constants.MEME_PERSON_CATEGORIES)
    assert all(line[2] in constants.MEME_POSITIONS and line in prompt for line in section)
    assert "\n\n# 行動原理\nモックprinciple" in record.text


def test_generate_non_person_draws_from_its_own_categories(session, monkeypatch):
    place = _place(session)
    _one_meme_per_category(session, monkeypatch)
    ai = MockAIClient(seed=2)

    record = _generate_one(session, place, Stamp(2100, 1, 1), random.Random(2), ai, person=False)

    prompt = next(c for c in ai.calls if c["system"] == _NON_PERSON_CONTENT_SYSTEM_PROMPT)["prompt"]
    assert "この対象の行動原理(ミーム。" in prompt
    for category in MEME_CATEGORIES:
        assert (f"{category}のミーム" in record.text) == (category in constants.MEME_NON_PERSON_CATEGORIES)


def test_generate_without_memes_leaves_no_meme_sections(session):
    place = _place(session)
    ai = MockAIClient(seed=1)

    record = _generate_one(session, place, Stamp(2100, 1, 1), random.Random(1), ai, person=True)

    assert "# meme" not in record.text and "# 行動原理" not in record.text
    assert all("行動原理(ミーム。" not in c["prompt"] for c in ai.calls)


def test_generate_person_decides_dialect_and_passes_it_to_naming(session):
    place = _place(session)
    ai = MockAIClient(seed=1)

    record = _generate_one(session, place, Stamp(2100, 1, 1), random.Random(1), ai, person=True)

    assert "dialect" in next(c for c in ai.calls if c["system"] == _CONTENT_SYSTEM_PROMPT)["schema"]["required"]
    assert record.dialect
    assert f"方言: {record.dialect}" in ai.calls[-1]["prompt"]
    session.expire_all()
    assert session.get(Character, record.id).dialect == record.dialect


def test_generate_non_person_has_no_dialect(session):
    place = _place(session)
    ai = MockAIClient(seed=2)

    record = _generate_one(session, place, Stamp(2100, 1, 1), random.Random(2), ai, person=False)

    assert record.dialect is None
    assert all("方言: " not in c["prompt"] for c in ai.calls)


def test_history_section_writes_the_year_and_age_of_each_step_up_to_now():
    items = [
        {"age": 14, "text": "関所に雇われる。"},
        {"age": 0, "text": "隊商宿に生まれる。"},
        {"age": 40, "text": "先の歳は捨てる。"},
        {"age": 3, "text": ""},
    ]

    assert history_section(items, 11538, 30) == (
        "- 11538年(0歳): 隊商宿に生まれる。\n"
        "- 11552年(14歳): 関所に雇われる。\n"
        "- 11568年(30歳): 現在。"
    )


def test_history_section_marks_the_last_step_at_the_current_age_as_now():
    items = [{"age": 0, "text": "生まれる。"}, {"age": 20, "text": "港で荷を担ぐ。"}]

    assert history_section(items, 2080, 20).splitlines()[-1] == "- 2100年(20歳): 現在。港で荷を担ぐ。"


class _TellsHistory(MockAIClient):
    def try_generate_json(self, prompt, schema, **kwargs):
        decided = super().try_generate_json(prompt, schema, **kwargs)
        if kwargs.get("system") == _CONTENT_SYSTEM_PROMPT:
            decided["age"] = 20
            decided["history"] = [{"age": 0, "text": "【名前】が生まれる。"},
                                  {"age": 20, "text": "港で荷を担ぐ。"}]
        return decided


def test_generate_person_writes_the_history_before_the_memes(session, monkeypatch):
    place = _place(session)
    _one_meme_per_category(session, monkeypatch)

    record = _generate_one(session, place, Stamp(2100, 1, 1), random.Random(1), _TellsHistory(seed=1), person=True)

    assert f"\n\n# 来歴\n- 2080年(0歳): {record.name}が生まれる。\n- 2100年(20歳): 現在。港で荷を担ぐ。\n\n# meme\n" in record.text


def test_generate_non_person_has_no_history(session):
    place = _place(session)

    record = _generate_one(session, place, Stamp(2100, 1, 1), random.Random(2), MockAIClient(seed=2), person=False)

    assert "# 来歴" not in record.text
