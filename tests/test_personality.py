import pytest

from db.schema import (
    PERSONALITY_COLUMNS, PERSONALITY_DEFAULT, PERSONALITY_LEVELS, Character, CharacterParameter,
    PersonalityLevel, check_personality,
)
from randomizer.mock_factories import CharacterParameterFactory
from randomizer.random_character_generator import build_character, build_parameter


def test_levels_are_five_stages_in_order():
    assert PERSONALITY_LEVELS == ("無", "低", "並", "高", "必")
    assert PERSONALITY_DEFAULT == "並"
    assert [level.value for level in PersonalityLevel] == list(PERSONALITY_LEVELS)


def test_personality_columns_are_nullable_strings():
    columns = CharacterParameter.__table__.columns
    assert len(PERSONALITY_COLUMNS) == 12
    for name in PERSONALITY_COLUMNS:
        column = columns[name]
        assert column.type.python_type is str
        assert column.nullable is True
        assert name not in Character.__table__.columns


def test_character_without_parameters_gets_default_level(session):
    record = Character(name="x", text="")
    session.add(record)
    session.flush()
    session.refresh(record)
    assert all(record.parameters_at()[name] == PERSONALITY_DEFAULT for name in PERSONALITY_COLUMNS)


@pytest.mark.parametrize("data", [
    {},
    {"name": "x"},
    {"sincerity": "無", "imagination": "必"},
    {name: "並" for name in PERSONALITY_COLUMNS},
    {"sincerity": None},
])
def test_check_personality_accepts_levels(data):
    check_personality(data)


@pytest.mark.parametrize("bad", [
    {"sincerity": 0},
    {"curiosity": 3},
    {"sincerity": "中"},
    {"sincerity": "高", "imagination": "とても高い"},
])
def test_check_personality_rejects_non_levels(bad):
    with pytest.raises(ValueError, match="無/低/並/高/必"):
        check_personality(bad)


def _assert_levels(draws):
    for draft in draws:
        for name in PERSONALITY_COLUMNS:
            assert draft[name] in PERSONALITY_LEVELS, (name, draft[name])
    # 100 件も引けば一つの軸に二つ以上の段階が出る(常に同じ値を返していない)
    assert len({draft["sincerity"] for draft in draws}) > 1


def test_build_character_draws_levels():
    drafts = [build_character() for _ in range(100)]
    assert all(len(draft["parameters"]) == 1 for draft in drafts)
    assert all(draft["parameters"][0]["start"] is None and draft["parameters"][0]["end"] is None
               for draft in drafts)
    _assert_levels([draft["parameters"][0] for draft in drafts])


def test_build_parameter_overrides_keep_levels():
    assert build_parameter(sincerity="必")["sincerity"] == "必"


def test_mock_factory_draws_levels():
    rows = [CharacterParameterFactory.build(character_id=1) for _ in range(100)]
    _assert_levels([{name: getattr(row, name) for name in PERSONALITY_COLUMNS} for row in rows])
