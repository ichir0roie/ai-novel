#!/usr/bin/env python3
"""schema.py の全テーブルぶんの factory_boy ファクトリ(モックデータ用)。

    from DEM.randomizer import mock_factories as mf
    mf.bind(engine)                # 書き込み先を差す
    mf.LocationFactory.create_batch(100)
    mf.commit()

外部キーは、その時点で db に居る行から無作為に選ぶ。まだ一件も無ければ
参照先のファクトリで作って埋める(nullable な列は一定の割合で None にする)。
"""
from __future__ import annotations

import factory
from factory.random import randgen
from sqlalchemy import select
from sqlalchemy.orm import scoped_session, sessionmaker

from DEM.db.schema import (
    CHARACTER_KIND_PERSON,
    Character, CharacterPlace, CharacterPlot, Episode, Event, EventCharacter,
    Location, Plot, Story, Term,
)
from DEM.db.stamp import Stamp
from DEM.randomizer.random_character_generator import (
    _BUILD_CHOICES, _FIRST_PERSON_CHOICES, _PERSONALITY_RANGE,
    _SECOND_PERSON_CHOICES, _SEX_CHOICES, _THIRD_PERSON_CHOICES, _TONE_CHOICES,
)

_session = scoped_session(sessionmaker())

_LOCALE = "ja_JP"
_YEAR_RANGE = (4000, 5000)

_LOCATION_KINDS = ("世界線", "惑星", "大陸", "国", "地方", "都市", "町", "村", "森", "山", "海", "島")
_ENVIRONMENTS = ("温帯", "寒帯", "乾燥帯", "熱帯", "高地", "沿岸", "湿地", "砂漠", "凍土")
_SAMPLE_REGIONS = ("北欧", "地中海沿岸", "東アジア", "中東", "南米", "東欧", "東南アジア", "北米平原")
_SAMPLE_CULTURES = ("遊牧", "稲作", "狩猟採集", "交易", "漁労", "牧畜", "都市商業")
_SAMPLE_ERAS = ("古代", "中世", "近世", "産業革命期", "近代", "現代", "近未来")
_CHARACTER_KINDS = (CHARACTER_KIND_PERSON,) * 7 + ("国", "組織", "商会", "氏族", "集団", "物")
_TERM_KINDS = ("地名", "人名", "組織", "技術", "魔法", "制度", "道具", "生物", "慣習")
_NARRATIONS = ("一人称", "三人称", "神視点")
_STATES = ("構想中", "執筆中", "完結", "中断")


def bind(engine) -> None:
    _session.configure(bind=engine)


def commit() -> None:
    _session.commit()
    _session.remove()


def _random_stamp(after: Stamp | None = None) -> Stamp:
    low = after.year if after is not None else _YEAR_RANGE[0]
    year = randgen.randint(low, max(low, _YEAR_RANGE[1]))
    return Stamp(year, randgen.randint(1, 12), randgen.randint(1, 28),
                 randgen.randint(0, 23), randgen.randint(0, 59), randgen.randint(0, 59))


def _pick_id(model, factory_class=None, p_none: float = 0.0):
    if p_none and randgen.random() < p_none:
        return None
    ids = _session().execute(select(model.id)).scalars().all()
    if ids:
        return randgen.choice(ids)
    if factory_class is None:
        return None
    return factory_class().id


def _pool(model, factory_name: str | None = None, p_none: float = 0.0):
    # 参照先のファクトリはこの後で定義されるので、名前で持って呼ぶときに引く
    return factory.LazyFunction(
        lambda: _pick_id(model, globals()[factory_name] if factory_name else None, p_none))


def _stamp():
    return factory.LazyFunction(_random_stamp)


def _optional_stamp(p_none: float = 0.3):
    return factory.LazyFunction(
        lambda: None if randgen.random() < p_none else _random_stamp())


def _end_after_start(p_none: float = 0.5):
    return factory.LazyAttribute(
        lambda o: None if o.start is None or randgen.random() < p_none
        else _random_stamp(after=o.start))


def _text():
    return factory.Faker("text", max_nb_chars=200, locale=_LOCALE)


class _ModelFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session = _session
        sqlalchemy_session_persistence = "flush"


class LocationFactory(_ModelFactory):
    class Meta:
        model = Location

    name = factory.Sequence(lambda n: f"土地{n}")
    kind = factory.Faker("random_element", elements=_LOCATION_KINDS)
    text = _text()
    parent_id = _pool(Location, p_none=0.15)

    location_world = factory.Faker("random_int", min=0, max=9)
    location_planet = factory.Faker("random_int", min=0, max=5)
    location_longitude = factory.Faker("pyfloat", min_value=-180, max_value=180, right_digits=3)
    location_latitude = factory.Faker("pyfloat", min_value=-90, max_value=90, right_digits=3)
    location_altitude = factory.Faker("pyfloat", min_value=0, max_value=3000, right_digits=1)

    area = factory.Faker("pyfloat", min_value=1, max_value=1_000_000, right_digits=1)
    environment = factory.Faker("random_element", elements=_ENVIRONMENTS)
    sample_region = factory.Faker("random_element", elements=_SAMPLE_REGIONS)
    sample_culture = factory.Faker("random_element", elements=_SAMPLE_CULTURES)
    sample_era = factory.Faker("random_element", elements=_SAMPLE_ERAS)

    start = _optional_stamp()
    end = _end_after_start()
    active_random_generation = factory.Faker("pybool")


class CharacterFactory(_ModelFactory):
    class Meta:
        model = Character
        # `build` は Character の列名と `Factory.build()` が衝突する
        rename = {"build_": "build"}

    name = factory.Faker("name", locale=_LOCALE)
    read = factory.Faker("kana_name", locale=_LOCALE)
    kind = factory.Faker("random_element", elements=_CHARACTER_KINDS)
    text = _text()
    world_influence = factory.Faker("random_int", min=0, max=5)

    start = _optional_stamp()
    end = _end_after_start()

    sex = factory.Faker("random_element", elements=_SEX_CHOICES)
    height = factory.Faker("pyfloat", min_value=140, max_value=195, right_digits=1)
    build_ = factory.Faker("random_element", elements=_BUILD_CHOICES)

    first_person = factory.Faker("random_element", elements=_FIRST_PERSON_CHOICES)
    second_person = factory.Faker("random_element", elements=_SECOND_PERSON_CHOICES)
    third_person = factory.Faker("random_element", elements=_THIRD_PERSON_CHOICES)
    tone = factory.Faker("random_element", elements=_TONE_CHOICES)

    sincerity = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    curiosity = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    proactivity = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    cooperativeness = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    sociability = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    emotional_expression = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    self_esteem = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    self_efficacy = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    stress_resilience = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    flexibility_of_values = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    sensitivity = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    imagination = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])


class EventFactory(_ModelFactory):
    class Meta:
        model = Event

    name = factory.Sequence(lambda n: f"出来事{n}")
    hidden = factory.Faker("boolean", chance_of_getting_true=10)
    text = _text()
    time = _stamp()
    parent_event_id = _pool(Event, p_none=0.3)
    location_id = _pool(Location, "LocationFactory", p_none=0.1)
    start = _optional_stamp()
    end = _end_after_start()


class EventCharacterFactory(_ModelFactory):
    class Meta:
        model = EventCharacter

    event_id = _pool(Event, "EventFactory")
    character_id = _pool(Character, "CharacterFactory")


class PlotFactory(_ModelFactory):
    class Meta:
        model = Plot

    text = _text()
    location_id = _pool(Location, "LocationFactory", p_none=0.1)
    start = _optional_stamp()
    end = _end_after_start()


class CharacterPlaceFactory(_ModelFactory):
    class Meta:
        model = CharacterPlace

    character_id = _pool(Character, "CharacterFactory")
    location_id = _pool(Location, "LocationFactory")
    start = _optional_stamp()
    end = _end_after_start()


class CharacterPlotFactory(_ModelFactory):
    class Meta:
        model = CharacterPlot

    text = _text()
    character_id = _pool(Character, "CharacterFactory")
    start = _optional_stamp()
    end = _end_after_start()


class TermFactory(_ModelFactory):
    class Meta:
        model = Term

    name = factory.Sequence(lambda n: f"語{n}")
    kind = factory.Faker("random_element", elements=_TERM_KINDS)
    text = _text()
    restrict_world_id = _pool(Location, "LocationFactory", p_none=0.5)
    restrict_planet_id = _pool(Location, "LocationFactory", p_none=0.5)
    restrict_place_id = _pool(Location, "LocationFactory", p_none=0.5)
    parent_term_id = _pool(Term, p_none=0.3)


class StoryFactory(_ModelFactory):
    class Meta:
        model = Story

    name = factory.Sequence(lambda n: f"作品{n}")
    text = _text()
    world_id = _pool(Location, "LocationFactory", p_none=0.1)
    place_id = _pool(Location, "LocationFactory", p_none=0.1)
    narration = factory.Faker("random_element", elements=_NARRATIONS)
    state = factory.Faker("random_element", elements=_STATES)
    start = _optional_stamp()
    end = _end_after_start()


class EpisodeFactory(_ModelFactory):
    class Meta:
        model = Episode

    story_id = _pool(Story, "StoryFactory")
    number = factory.Sequence(lambda n: n + 1)
    title = factory.Faker("sentence", nb_words=4, locale=_LOCALE)
    text = factory.Faker("text", max_nb_chars=1000, locale=_LOCALE)
    letters = factory.LazyAttribute(lambda o: len(o.text))
    synced = factory.Faker("pybool")


# 外部キーの参照先が先に埋まる順
ALL_FACTORIES = (
    LocationFactory,
    CharacterFactory,
    EventFactory,
    EventCharacterFactory,
    PlotFactory,
    CharacterPlaceFactory,
    CharacterPlotFactory,
    TermFactory,
    StoryFactory,
    EpisodeFactory,
)
