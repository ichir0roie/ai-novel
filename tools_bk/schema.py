#!/usr/bin/env python3
from __future__ import annotations

import os

from sqlalchemy import (
    BigInteger, Boolean, Integer, String, DECIMAL, TypeDecorator,
    create_engine, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from stamp import Stamp


class StampType(TypeDecorator):
    """作中の時刻。**桁を並べた整数として持つ。**
    python の `datetime` は 9999 年までしか持てず、作中の暦はそれを越える。
    `tools/stamp.py` の `Stamp` を、`年月日時分秒` を並べた整数へ落として入れる。
    並びがそのまま時の前後になるので、`ORDER BY` も `<` もそのまま効く。
    """

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        parsed = Stamp.parse(value)
        if parsed is None:
            raise ValueError(f"Invalid stamp value: {value}")
        return parsed.to_int()

    def process_result_value(self, value, dialect):
        return Stamp.from_int(value)


LOCATION_COLUMNS = ("location_world", "location_planet",
                    "location_longitude", "location_latitude",
                    "location_altitude")

_LOCATION_TAGS = ("w", "p", "lon", "lat", "alt")


def _digit(value) -> str:
    """`4.0` を `4` に寄せて、座標を見た目の揺れなく並べる。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    return str(int(number)) if number == int(number) else repr(number)


def location_text(values) -> str | None:
    """**場所の一意テキスト。** `w/p/lon/lat/alt` を並べて一本の文字列にする。

    `values` は辞書でもレコードの行でもよい。欠けている桁は `-` で埋める。
    どの桁も無ければ `None`（座標を持たない場所）。

    `w4/p1/lon12/lat-/alt-` のように、上から順に並ぶ。前方一致がそのまま
    「同じ世界線」「同じ星」の絞り込みになる。
    """
    get = values.get if hasattr(values, "get") else (
        lambda column: getattr(values, column, None))
    parts = [get(column) for column in LOCATION_COLUMNS]
    if all(part in (None, "") for part in parts):
        return None
    return "/".join(
        tag + ("-" if part in (None, "") else _digit(part))
        for tag, part in zip(_LOCATION_TAGS, parts))


class MarkdownBase(DeclarativeBase):
    text: Mapped[str] = mapped_column(String,  nullable=False)

    filepath: Mapped[str] = mapped_column(
        String, primary_key=True,
        comment="主キー。**置き場所そのもの**（novels/ からの相対パス、拡張子なし）。"
                "md には書かない。読み込むときに置き場所から入る")


class RecordBase(DeclarativeBase):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class Place(MarkdownBase):
    """
    novels/worlds/{place_name}/**/{place_name}.md
    """

    __tablename__ = "place"

    name: Mapped[str | None] = mapped_column(String)
    kind: Mapped[str | None] = mapped_column(String)
    parent_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    # 位置は**一つの座標系だけ**で持つ。経度・緯度・高度で持ち、
    # **どこを原点とするかは星ごとに決めて、その星の md に書く**。
    location_world: Mapped[float | None] = mapped_column(DECIMAL, comment="世界線番号 W")
    location_planet: Mapped[int | None] = mapped_column(Integer, comment="惑星番号 P")
    location_longitude: Mapped[float | None] = mapped_column(
        DECIMAL, comment="経度。基準の子午線から東へ何度（西は負）")
    location_latitude: Mapped[float | None] = mapped_column(
        DECIMAL, comment="緯度。赤道から北へ何度（南は負）")
    location_altitude: Mapped[float | None] = mapped_column(
        DECIMAL, comment="高度。基準面から上へ何 m")

    location_key: Mapped[str | None] = mapped_column(
        String, unique=True, index=True,
        comment="場所の一意テキスト。`w/p/lon/lat/alt` を並べて文字列にしたもの。"
                "md には書かない。読み込みのときに組み立てる（location_text）")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Event(MarkdownBase):
    """
    novels/worlds/{place_name}/**/events/{yyyymmddhhmmss}_{event_name}.md
    novels/objects/{world_name}/**/{object_name}/events/{yyyymmddhhmmss}_{action_name}.md
    novels/characters/{born_place_name}/**/{character_name}/events/{yyyymmddhhmmss}_{action_name}.md

    **起きたことは、ぜんぶここに入る。** 場所で起きたことも、人物・個体が
    したことも同じ表。行動は `character_id` / `object_id` が誰かを持ち、
    掛かり先の出来事を `parent_event_id` が指す。
    ある時刻・ある場所の要素は `place` と結んで一度に引ける。
    """

    __tablename__ = "event"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="")
    time: Mapped[Stamp] = mapped_column(StampType, index=True)

    parent_event_id: Mapped[str | None] = mapped_column(String, ForeignKey("event.id"))

    place_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("place.id"), index=True)
    place: Mapped[Place | None] = relationship(lazy="noload")

    # **行動もここに入る。** 人物・個体の行動は別表を持たない。
    # 誰の行動かをこの二つが持ち、掛かり先の出来事は `parent_event_id`。
    # どちらも空なら、誰の行動でもない「ただ起きたこと」。
    character_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("character.id"), index=True,
        comment="その行動をした人物")
    object_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("object.id"), index=True,
        comment="その行動をした個体（群）")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)

    parent_event: Mapped["Event | None"] = relationship(
        remote_side="Event.id", back_populates="child_events", lazy="noload"
    )
    child_events: Mapped[list["Event"]] = relationship(
        back_populates="parent_event", lazy="selectin", cascade="all, delete-orphan"
    )


class Kind(MarkdownBase):
    """
    novels/objects/{root_place_name}/{kind_name}.md

    **型。** 何であるかの分類（系統・国・組織・仕組み）。
    個体はこの型にぶら下がる。
    """

    __tablename__ = "kind"

    name: Mapped[str] = mapped_column(String)
    read: Mapped[str] = mapped_column(String)


class ObjectBase:
    root_place_name: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    name: Mapped[str | None] = mapped_column(String)
    read: Mapped[str | None] = mapped_column(String)

    kind_id: Mapped[str | None] = mapped_column(String, ForeignKey("kind.id"))

    world_influence: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="世界線への影響度。大きいほど世界線を変える")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Object(MarkdownBase, ObjectBase):
    """
    novels/objects/{world_name}/**/{object_name}/{object_name}.md

    **種族・組織・仕組みなど、まとまりとして振る舞うもの。**
    一人ひとりの人間は `Character` が持つ。ここは群としての行動を持つ。
    """
    __tablename__ = "object"


class ObjectPlace(MarkdownBase):
    """
    {object_name}/places/{yyyymmddhhmmss}_{place_name}.md
    """

    __tablename__ = "object_place"

    object_id: Mapped[str | None] = mapped_column(String, ForeignKey("object.id"))
    place_id: Mapped[str] = mapped_column(String, ForeignKey("place.id"))

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Character(MarkdownBase, ObjectBase):
    """
    novels/characters/{born_place_name}/**/{character_name}/{character_name}.md

    **一人ひとりの人間。** 本文で一人称・二人称・三人称を書き分けるために、
    ここがいちばん細かい。群としての振る舞いは `Object` の側にある。
    """

    __tablename__ = "character"

    # --- 出自 -------------------------------------------------------------
    born_place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    belong_id: Mapped[str | None] = mapped_column(String, ForeignKey("object.id"), comment="所属。個体のどれか")

    # --- 体格 -------------------------------------------------------------
    sex: Mapped[str] = mapped_column(String,  comment="性別")
    height: Mapped[float | None] = mapped_column(DECIMAL, comment="背丈 cm")
    build: Mapped[str] = mapped_column(String,  comment="体格")
    race_id: Mapped[str | None] = mapped_column(String, ForeignKey("kind.id"), comment="種族。種別のどれか")

    # --- 口調 -------------------------------------------------------------
    first_person: Mapped[str] = mapped_column(String,  comment="一人称")
    second_person: Mapped[str] = mapped_column(String,  comment="二人称")
    tone: Mapped[str] = mapped_column(String,  comment="口調")

    # --- 性格 -----------------------------------------------------------
    sincerity: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="誠実性")
    curiosity: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="好奇心")
    proactivity: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="行動力")
    cooperativeness: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="協調性")
    sociability: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="社交性")
    emotional_expression: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="感情表現")
    self_esteem: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="自己肯定感")
    self_efficacy: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="自己効力感")
    stress_resilience: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="ストレス耐性")
    flexibility_of_values: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="価値観の柔軟性")
    sensitivity: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="感受性")
    imagination: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="想像力")

    # relationships

    places: Mapped[list[ObjectPlace]] = relationship(
        back_populates="Character", lazy="selectin", cascade="all, delete-orphan", order_by="ObjectPlace.start.desc()"
    )
    skills: Mapped[list[CharacterSkill]] = relationship(lazy="selectin", cascade="all, delete-orphan", order_by="CharacterSkill.id.asc()")


class CharacterPlace(MarkdownBase):
    """
    {character_name}/places/{yyyymmddhhmmss}_{place_name}.md
    """

    __tablename__ = "character_place"

    character_id: Mapped[str | None] = mapped_column(String, ForeignKey("character.id"))
    place_id: Mapped[str] = mapped_column(String, ForeignKey("place.id"))

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Skill(MarkdownBase):
    """
    novels/skills/{skill_name}/{skill_name}.md

    **技能。** 何ができるかの分類（戦闘・魔法・工作・交渉）。
    個体はこの技能にぶら下がる。
    """

    __tablename__ = "skill"

    name: Mapped[str] = mapped_column(String)

    # 現象、コスト、効果、範囲、持続時間、対象、条件、制約
    cost: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="コスト")
    effect: Mapped[str] = mapped_column(String, nullable=False, comment="効果")
    range: Mapped[str] = mapped_column(String, comment="範囲")
    duration: Mapped[str] = mapped_column(String, comment="持続時間")
    target: Mapped[str] = mapped_column(String, comment="対象")
    constraint: Mapped[str] = mapped_column(String,  comment="制約")


class CharacterSkill(RecordBase):

    __tablename__ = "character_skill"

    character_id: Mapped[str | None] = mapped_column(String, ForeignKey("character.id"))
    object_id: Mapped[str | None] = mapped_column(String, ForeignKey("object.id"))

    skill_id: Mapped[str] = mapped_column(String, ForeignKey("skill.id"), nullable=False)

    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="熟練度")


class Term(MarkdownBase):
    """
    novels/terms/**/{term_name}/{term_name}.md

    **入れ子。** ディレクトリが上下を表す。`{term_name}/{term_name}.md` がその語、
    その下のディレクトリがその語にぶら下がる語。
    """
    __tablename__ = "term"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)

    restrict_world_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    restrict_planet_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    restrict_place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    parent_term_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("term.id"), comment="上位の語。置いたディレクトリで決まる")


class Story(MarkdownBase):
    """
    novels/stories/{story_name}/meta.md

    **作品。** 本文の入れ物。どの世界線のどこに立つかをここが持つ。
    作品は世界線をまたがない。
    """

    __tablename__ = "story"

    name: Mapped[str] = mapped_column(String)

    world_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("place.id"), comment="使用する世界線")
    place_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("place.id"), comment="立つ場所。断面を取るのに使う")
    narration: Mapped[str] = mapped_column(String,  comment="語り")
    state: Mapped[str] = mapped_column(String,  comment="状態")

    start: Mapped[Stamp | None] = mapped_column(StampType, comment="立つ年")
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Episode(MarkdownBase):
    """
    novels/stories/{story_name}/episodes/{話数}.md

    **一話。** `text` が原稿そのもの。データは `同期` だけを持つ。
    話数はファイル名、題と字数は原稿から採る（書き戻すときも足さない）。
    """

    __tablename__ = "episode"

    story_id: Mapped[str] = mapped_column(String, ForeignKey("story.id"))
    number: Mapped[int | None] = mapped_column(
        Integer, comment="話数。ファイル名の数がそのまま入る。**ゼロ埋めしない**")
    title: Mapped[str] = mapped_column(
        String,  comment="サブタイトル。本文の見出しから読む")
    letters: Mapped[int | None] = mapped_column(Integer, comment="字数")
    synced: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="同期フラグ。この話の出来事・行動が台帳へ戻してあるか。"
                "自動生成時はオン、手で書いたときはオフ。"
                "オフの話があるあいだは、次の話の材料を読み出せない")


def create_db(path):
    """**db ファイルを作り直して、空のテーブルを張る。**

    台帳から何度でも組み直せるので、既にあれば消して作り直す。
    """
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    engine = create_engine(f"sqlite:///{path}", future=True)
    MarkdownBase.metadata.create_all(engine)
    return engine


def open_db(path):
    """既にある db を開く。"""
    return create_engine(f"sqlite:///{os.path.abspath(path)}", future=True)
