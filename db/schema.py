#!/usr/bin/env python3
from __future__ import annotations

import enum
import hashlib
import os

from sqlalchemy import (
    BigInteger, Boolean, Integer, String, DECIMAL, JSON, TypeDecorator,
    create_engine,
    ForeignKey,
    UniqueConstraint,
    select,
    Select,
    text,
    update,
    or_,
    and_,
    delete,
)
from sqlalchemy.orm import (
    Session,
    joinedload,
    selectinload,
    lazyload,
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from sqlalchemy import func

from db.polygon import parse_polygon
from db.stamp import Stamp


class StampType(TypeDecorator):

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


class PolygonType(TypeDecorator):

    impl = JSON
    cache_ok = True

    def __init__(self):
        # 既定だと None が JSON の 'null' 文字列で入り、IS NULL で引けなくなる
        super().__init__(none_as_null=True)

    def process_bind_param(self, value, dialect):
        return parse_polygon(value)


LOCATION_COLUMNS = ("location_world", "location_planet",
                    "location_longitude", "location_latitude",
                    "location_altitude")

_LOCATION_TAGS = ("w", "p", "lon", "lat", "alt")


def _digit(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    return str(int(number)) if number == int(number) else repr(number)


def location_text(values) -> str | None:
    """`w4/p1/lon12/lat-/alt-` のように、上から順に並ぶ。前方一致がそのまま
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


class Base(DeclarativeBase):

    # SQLite は「INTEGER PRIMARY KEY」だけを rowid の別名として autoincrement する。
    # Integer だと型名が INTEGER と一致せず insert のたびに id が NULL のまま失敗する。
    # sort_order は列の並び順を明示するための番号。継承の段が一段深くなるごとに
    # 開始値を 100 増やし、同じクラス内では 10 刻みで振る(あとで列を挟みやすい)。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, sort_order=0)


class MarkdownBase(Base):
    __abstract__ = True

    # md 側で `# <名前>` の節として出し入れする列。`# data` には出さない
    TEXT_SECTIONS: tuple[str, ...] = ("text",)

    text: Mapped[str] = mapped_column(String,  nullable=False, sort_order=10000)

    directory_path: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, sort_order=20000,
        comment="import,export時の配置先。worlds/{table}/ からの相対ディレクトリパス。"
                "空ならテーブル直下に置く")
    filename: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, sort_order=20010,
        comment="import,export時のファイル名(id・拡張子を除いた部分)。"
                "空なら {id}.md。テーブルが持つ name 等の列とは別物")

    def default_filename(self) -> str | None:
        return None

    @property
    def markdown_name(self) -> str:
        name = self.filename or self.default_filename()
        return f"{self.id}_{name.replace('/', '／')}.md" if name else f"{self.id}.md"

    @classmethod
    def parse_markdown_stem(cls, stem: str) -> tuple[int | None, dict]:
        id_part, _, filename_part = stem.partition("_")
        if id_part.isdigit():
            return int(id_part), {"filename": filename_part or None}
        return None, {"filename": stem}


class Location(MarkdownBase):

    __tablename__ = "location"

    name: Mapped[str | None] = mapped_column(String, sort_order=200)
    kind: Mapped[str | None] = mapped_column(String, sort_order=210)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"), sort_order=220)

    # 位置は**一つの座標系だけ**で持つ。経度・緯度・高度で持ち、
    # **どこを原点とするかは星ごとに決めて、その星の md に書く**。
    location_world: Mapped[float | None] = mapped_column(DECIMAL, comment="世界線番号 W", sort_order=230)
    location_planet: Mapped[int | None] = mapped_column(Integer, comment="惑星番号 P", sort_order=240)
    location_longitude: Mapped[float | None] = mapped_column(DECIMAL, comment="経度。基準の子午線から東へ何度(西は負)", sort_order=250)
    location_latitude: Mapped[float | None] = mapped_column(DECIMAL, comment="緯度。赤道から北へ何度(南は負)", sort_order=260)
    location_altitude: Mapped[float | None] = mapped_column(DECIMAL, comment="高度。基準面から上へ何 m", sort_order=270)
    polygon: Mapped[dict | None] = mapped_column(
        PolygonType, comment="輪郭。GeoJSON の Polygon(`coordinates` は [経度, 緯度] の環の並び、"
        "先頭が外周で以降は穴)。地図では面として描く。経緯度が無くても持てる", sort_order=280)

    area: Mapped[float | None] = mapped_column(
        DECIMAL, comment="広さ。単位は決めていないが、親と子で揃える。"
        "子の広さは親未満、兄弟(同じ parent_id)を足しても親を超えない", sort_order=290)
    environment: Mapped[str | None] = mapped_column(String, comment="環境", sort_order=300)

    sample_region: Mapped[str | None] = mapped_column(
        String, comment="参考にした実在の地域(例: 「北欧」「地中海沿岸」)。"
        "固有名詞をそのまま使うのではなく、地理・気候・景観の手がかりとして持つ", sort_order=305)
    sample_culture: Mapped[str | None] = mapped_column(
        String, comment="参考にした実在の文化(例: 「遊牧」「稲作」)。"
        "風習・生活様式・価値観の手がかりとして持つ", sort_order=307)
    sample_era: Mapped[str | None] = mapped_column(
        String, comment="参考にした実在の時代(例: 「中世」「産業革命期」)。"
        "技術水準・社会制度の手がかりとして持つ", sort_order=308)

    start: Mapped[Stamp | None] = mapped_column(StampType, sort_order=310)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=320)

    active_random_generation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 自分の親(一つ上の場所)。木をのぼって道筋(place_path)を組むのに使う。
    # 書き込みは常に parent_id を直に触るので、どちらも読み取り専用にしておく
    # (viewonly を外すと、同じ外部キーを double-write しようとして SQLAlchemy が警告する)。
    parent: Mapped["Location | None"] = relationship(
        remote_side="Location.id", viewonly=True, lazy="noload")
    children: Mapped[list[Location]] = relationship(viewonly=True)

    def default_filename(self) -> str | None:
        return self.name


class EventSeededMixin:
    event_seeded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="出来事の種を抜き出し済みか。false に戻すと、次の毎日のルーチンで抜き出し直す",
        sort_order=9000)


class MemeSeededMixin:
    meme_seeded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="ミームを抜き出し済みか。false に戻すと、次の抽出で抜き出し直す",
        sort_order=9010)


class FactCheckMixin:
    TEXT_SECTIONS = ("text", "fact_check")

    fact_check: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="AI が Dラボ・ネット検索で検めた妥当性と補足。空ならまだ検めていない",
        sort_order=10010)


class Event(EventSeededMixin, MemeSeededMixin, MarkdownBase):

    __tablename__ = "event"

    name: Mapped[str] = mapped_column(String, sort_order=200)
    # 断面(ReadBrief)に出すかどうかだけを持つ。分類は name/text の書き方で表す。
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, sort_order=210)
    time: Mapped[Stamp] = mapped_column(StampType, index=True, sort_order=220)

    parent_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("event.id"), sort_order=230)

    location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), index=True, sort_order=240)
    location: Mapped[Location | None] = relationship(lazy="noload")

    # 行動もここに入る(人物の行動に別表は無い)。誰の行動かは
    # event_character(中間テーブル、多対多)が持つ。空なら
    # 誰の行動でもない「ただ起きたこと」。
    event_characters: Mapped[list["EventCharacter"]] = relationship(
        back_populates="event", lazy="noload", cascade="all, delete-orphan")

    start: Mapped[Stamp | None] = mapped_column(StampType, sort_order=250)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=260)

    parent_event: Mapped["Event | None"] = relationship(
        remote_side="Event.id", back_populates="child_events", lazy="noload"
    )
    child_events: Mapped[list["Event"]] = relationship(
        back_populates="parent_event", lazy="noload", cascade="all, delete-orphan"
    )


class EventCharacter(Base):
    __tablename__ = "event_character"

    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("event.id"), index=True, sort_order=100)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("character.id"), index=True, sort_order=110)

    event: Mapped["Event"] = relationship(back_populates="event_characters", lazy="noload")
    character: Mapped["Character"] = relationship(lazy="noload")


def summary_source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EventSummary(Base):
    __tablename__ = "event_summary"

    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("event.id"), unique=True, index=True, sort_order=100)
    source_hash: Mapped[str] = mapped_column(
        String, comment="要約した本文の sha256。本文と食い違ったら作り直す", sort_order=110)
    text: Mapped[str] = mapped_column(String, comment="要約", sort_order=120)


class EventSeed(Base):
    __tablename__ = "event_seed"

    text: Mapped[str] = mapped_column(String, comment="種", sort_order=100)
    consolidated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="棚卸し(似た種をまとめる)を済ませたか。新しい種は false", sort_order=110)


class MemeCategory(enum.StrEnum):
    BELIEF = "信条"
    DESIRE = "欲求"
    SITUATION = "境遇"
    GROUP = "集団"
    LAW = "理"


MEME_CATEGORIES = tuple(category.value for category in MemeCategory)


class Meme(FactCheckMixin, MarkdownBase):
    """ミームは移り変わり・伝染していくものなので、どの元から抜き出したか、どの人物が持つかは持たない
    (元の側の `meme_seeded` で、抜き出し済みかだけを管理する)。
    """

    __tablename__ = "meme"

    category: Mapped[str | None] = mapped_column(
        String, nullable=True,
        comment=f"分類。{'/'.join(MEME_CATEGORIES)} のいずれか。空なら次の抽出で AI が振る",
        sort_order=200)


class Oracle(FactCheckMixin, MemeSeededMixin, MarkdownBase):
    """著者自身の創作・AI についての覚え書き。物語のデータではない。"""

    __tablename__ = "oracle"


CHARACTER_KIND_PERSON = "人物"


class PersonalityLevel(enum.StrEnum):
    NONE = "無"
    LOW = "低"
    NORMAL = "並"
    HIGH = "高"
    MUST = "必"


PERSONALITY_LEVELS = tuple(level.value for level in PersonalityLevel)
PERSONALITY_DEFAULT = PersonalityLevel.NORMAL.value

PERSONALITY_COLUMNS = (
    "sincerity", "curiosity", "proactivity", "cooperativeness", "sociability",
    "emotional_expression", "self_esteem", "self_efficacy", "stress_resilience",
    "flexibility_of_values", "sensitivity", "imagination",
)


def check_personality(data) -> None:
    bad = {column: data[column] for column in PERSONALITY_COLUMNS
           if column in data and data[column] not in PERSONALITY_LEVELS}
    if bad:
        raise ValueError(
            f"性格は {'/'.join(PERSONALITY_LEVELS)} のいずれか: {bad}")


class Character(EventSeededMixin, MemeSeededMixin, MarkdownBase):
    """人物に限らず、国・組織・集団・物も一行として持つ(`kind` で区別)。

    ミームは人物どうしで移り変わり・伝染していくものなので、`Meme` 側との FK は持たない。
    """

    __tablename__ = "character"

    text: Mapped[str | None] = mapped_column(String, nullable=True, sort_order=10000)

    name: Mapped[str | None] = mapped_column(String, sort_order=210)
    kind: Mapped[str] = mapped_column(
        String, default=CHARACTER_KIND_PERSON, nullable=False,
        comment="種別。「人物」か、人物以外の対象(国・組織・商会・氏族・集団・物など)", sort_order=230)

    main_character: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="メインキャラクターか。"
        "出来事・筋書きのランダム生成は、この列が false(サブキャラクター)の人物・対象だけを対象にする",
        sort_order=240)

    start: Mapped[Stamp | None] = mapped_column(StampType, sort_order=250)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=260)

    # 出自(生まれの場所)は別列を持たず、CharacterPlace の一番古い行として表す。
    # 体格・口調は人物だけが持つ。人物以外の対象は空のまま。
    # --- 体格 -------------------------------------------------------------
    sex: Mapped[str | None] = mapped_column(String,  comment="性別", sort_order=320)
    height: Mapped[float | None] = mapped_column(DECIMAL, comment="背丈 cm", sort_order=330)
    build: Mapped[str | None] = mapped_column(String,  comment="体格", sort_order=340)

    # --- 口調 -------------------------------------------------------------
    first_person: Mapped[str | None] = mapped_column(String,  comment="一人称", sort_order=350)
    second_person: Mapped[str | None] = mapped_column(String,  comment="二人称", sort_order=360)
    third_person: Mapped[str | None] = mapped_column(String,  comment="三人称", sort_order=370)
    tone: Mapped[str | None] = mapped_column(String,  comment="口調", sort_order=380)
    dialect: Mapped[str | None] = mapped_column(
        String, comment="方言。方言の種類か、標準語で話すならその癖(語尾・言い回し・訛り)", sort_order=385)

    # --- 性格 -----------------------------------------------------------
    # 各列は PersonalityLevel の値(無/低/並/高/必)。
    sincerity: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="誠実性", sort_order=390)
    curiosity: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="好奇心", sort_order=400)
    proactivity: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="行動力", sort_order=410)
    cooperativeness: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="協調性", sort_order=420)
    sociability: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="社交性", sort_order=430)
    emotional_expression: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="感情表現", sort_order=440)
    self_esteem: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="自己肯定感", sort_order=450)
    self_efficacy: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="自己効力感", sort_order=460)
    stress_resilience: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="ストレス耐性", sort_order=470)
    flexibility_of_values: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="価値観の柔軟性", sort_order=480)
    sensitivity: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="感受性", sort_order=490)
    imagination: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="想像力", sort_order=500)

    def default_filename(self) -> str | None:
        return self.name

    # relationships

    places: Mapped[list[CharacterPlace]] = relationship(
        back_populates="character", lazy="noload", order_by="CharacterPlace.start.desc()"
    )
    events: Mapped[list[Event]] = relationship(
        secondary="event_character", viewonly=True, lazy="noload",
        order_by="Event.start.desc()"
    )


class CharacterPlace(Base):

    __tablename__ = "character_place"

    character_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("character.id"), sort_order=100)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"), sort_order=110)

    start: Mapped[Stamp | None] = mapped_column(StampType, sort_order=120)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=130)

    character: Mapped[Character | None] = relationship(back_populates="places", lazy="noload")
    place: Mapped[Location] = relationship(lazy="noload")


class CharacterRelation(MarkdownBase):
    """`character_id_1` から見た `character_id_2` との関係を一行で持つ。"""

    __tablename__ = "character_relation"

    character_id_1: Mapped[int] = mapped_column(
        Integer, ForeignKey("character.id"), index=True,
        comment="関係の主体となる人物", sort_order=100)
    character_id_2: Mapped[int] = mapped_column(
        Integer, ForeignKey("character.id"), index=True,
        comment="関係の相手となる人物", sort_order=110)
    relation: Mapped[str] = mapped_column(
        String, nullable=False, comment="関係の短い名前(母・師・宿敵 など)", sort_order=120)

    start: Mapped[Stamp | None] = mapped_column(
        StampType, comment="この関係が始まる時。空なら初めから", sort_order=130)
    end: Mapped[Stamp | None] = mapped_column(
        StampType, comment="この関係が終わる時。空なら続いている", sort_order=140)

    def default_filename(self) -> str | None:
        return f"{self.character_id_1}_{self.character_id_2}"

    character_1: Mapped["Character"] = relationship(
        foreign_keys="CharacterRelation.character_id_1", lazy="noload")
    character_2: Mapped["Character"] = relationship(
        foreign_keys="CharacterRelation.character_id_2", lazy="noload")


IDEA_CANDIDATE_DIRECTORY = "候補"


class Idea(FactCheckMixin, MemeSeededMixin, MarkdownBase):
    __tablename__ = "idea"

    name: Mapped[str] = mapped_column(String, sort_order=200)
    kind: Mapped[str] = mapped_column(String, comment="種別(技術・制度・概念など)", sort_order=210)
    auto_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="本文から自動で足した未確認のアイデアか。検索・生成には他と同じく出る。確かめたら false にする",
        sort_order=215)

    location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), index=True,
        comment="効く場所。この場所とその配下で効く。空ならどこにも効かない", sort_order=220)
    start: Mapped[Stamp | None] = mapped_column(
        StampType, comment="効き始める時刻。出来事の時刻と比べる。空なら始まりを限らない", sort_order=230)
    end: Mapped[Stamp | None] = mapped_column(
        StampType, comment="効き終わる時刻(この時刻からは効かない)。空なら終わりを限らない", sort_order=240)

    parent_idea_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("idea.id"), comment="上位のアイデア。置いたディレクトリで決まる", sort_order=250)

    def default_filename(self) -> str | None:
        return self.name


class Story(EventSeededMixin, MarkdownBase):

    __tablename__ = "story"

    name: Mapped[str] = mapped_column(String, sort_order=200)

    world_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), comment="使用する世界線", sort_order=210)
    world: Mapped[Location | None] = relationship(
        foreign_keys="Story.world_id", lazy="noload")
    place_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), comment="立つ場所。断面を取るのに使う", sort_order=220)
    place: Mapped[Location | None] = relationship(
        foreign_keys="Story.place_id", lazy="noload")
    narration: Mapped[str] = mapped_column(String,  comment="語り", sort_order=230)
    state: Mapped[str] = mapped_column(String,  comment="状態", sort_order=240)

    start: Mapped[Stamp | None] = mapped_column(StampType, comment="立つ年", sort_order=250)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=260)

    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="story", lazy="noload", order_by="Episode.number.asc()")

    def default_filename(self) -> str | None:
        return self.name


class Episode(EventSeededMixin, MarkdownBase):

    __tablename__ = "episode"

    TEXT_SECTIONS = ("key", "text")

    story_id: Mapped[int] = mapped_column(Integer, ForeignKey("story.id"), sort_order=200)
    story: Mapped[Story] = relationship(back_populates="episodes", lazy="noload")
    number: Mapped[int | None] = mapped_column(
        Integer, comment="話数。ファイル名の数がそのまま入る。**ゼロ埋めしない**", sort_order=210)
    title: Mapped[str] = mapped_column(
        String,  comment="サブタイトル。本文の見出しから読む", sort_order=220)
    letters: Mapped[int | None] = mapped_column(Integer, comment="字数", sort_order=230)
    synced: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="同期フラグ。この話の出来事・行動が台帳へ戻してあるか。"
                "自動生成時はオン、手で書いたときはオフ。"
                "オフの話があるあいだは、次の話の材料を読み出せない",
        sort_order=240)

    start: Mapped[Stamp | None] = mapped_column(StampType, comment="話が立つ時刻", sort_order=250)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=260)
    viewpoint: Mapped[str | None] = mapped_column(
        String, comment="視点。誰に寄って語るか(「ノア(十四歳)」「アウレア / ミレア」)", sort_order=270)
    place: Mapped[str | None] = mapped_column(
        String, comment="場所。自由記述(「ヴァレンツァ 外れの川」)", sort_order=280)

    key: Mapped[str] = mapped_column(
        String, nullable=False, default="", server_default="",
        comment="キーテキスト。作者が入れる、AI 生成前の種。md では `# key` の節",
        sort_order=9990)

    def default_filename(self) -> str | None:
        return self.title or None

    @property
    def markdown_name(self) -> str:
        head = f"{self.story_id}_{self.number}" if self.number is not None else f"{self.story_id}"
        return f"{head}_{self.title.replace('/', '／')}.md" if self.title else f"{head}.md"

    @classmethod
    def parse_markdown_stem(cls, stem: str) -> tuple[int | None, dict]:
        # 名前は id を持たない({story_id}_{number}_{title})。行の取り違えを避けるため id は `# data` から読む
        story_part, _, rest = stem.partition("_")
        if not story_part.isdigit():
            return super().parse_markdown_stem(stem)
        number_part, _, title_part = rest.partition("_")
        if number_part.isdigit():
            return None, {"story_id": int(story_part), "number": int(number_part),
                          "title": title_part or None}
        return None, {"story_id": int(story_part), "title": rest or None}


class EpisodeSummary(Base):
    __tablename__ = "episode_summary"

    story_id: Mapped[int] = mapped_column(Integer, ForeignKey("story.id"), index=True, sort_order=100)
    episode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("episode.id"), unique=True, index=True, sort_order=110)
    source_hash: Mapped[str] = mapped_column(
        String, comment="要約した本文の sha256。本文と食い違ったら作り直す", sort_order=120)
    summary: Mapped[str] = mapped_column(String, comment="概要", sort_order=130)
    style: Mapped[str] = mapped_column(String, comment="文体の覚え書き", sort_order=140)


class EventIdea(Base):
    """出来事の本文が踏まえたアイデア。md には出さない。"""

    __tablename__ = "event_idea"
    __table_args__ = (UniqueConstraint("event_id", "idea_id"),)

    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("event.id"), index=True, sort_order=100)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("idea.id"), index=True, sort_order=110)


class EpisodeIdea(Base):
    """話の本文が踏まえたアイデア。md には出さない。"""

    __tablename__ = "episode_idea"
    __table_args__ = (UniqueConstraint("episode_id", "idea_id"),)

    episode_id: Mapped[int] = mapped_column(Integer, ForeignKey("episode.id"), index=True, sort_order=100)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("idea.id"), index=True, sort_order=110)


class CharacterIdea(Base):
    """人物・対象の説明が踏まえたアイデア。md には出さない。"""

    __tablename__ = "character_idea"
    __table_args__ = (UniqueConstraint("character_id", "idea_id"),)

    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("character.id"), index=True, sort_order=100)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("idea.id"), index=True, sort_order=110)


IDEA_LINK_MODELS = {Event: EventIdea, Episode: EpisodeIdea, Character: CharacterIdea}


# 既定値は持たない。場所を取り違えると sqlite が空の db を黙って作るので、未設定なら import で止める。
WORLD_DIR = os.environ["DEM_WORLD_DIR"]
NOVEL_DB_PATH = os.environ.get("DEM_NOVEL_DB_PATH", os.path.join(WORLD_DIR, "novel.db"))
WORLDS_ROOT = os.environ.get("DEM_WORLDS_DIR", os.path.join(WORLD_DIR, "worlds"))
DB_PATH = os.environ.get("DEM_DB_PATH", NOVEL_DB_PATH)


def create_db(path=DB_PATH):
    """台帳から何度でも組み直せるので、既にあれば消して作り直す。"""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        # sqlite の既定も UTF-8 だが、文字化け事故を防ぐため明記しておく。
        # テーブルが空のうちしか効かないので create_all の前に打つ。
        conn.execute(text("PRAGMA encoding='UTF-8'"))
    Base.metadata.create_all(engine)
    return engine


TEST_DB_PATH = os.path.join(WORLD_DIR, "novel.test.db")


def _make_engine(path):
    return create_engine(f"sqlite:///{os.path.abspath(path)}")


engine = _make_engine(DB_PATH)
_fixed_engines = {}


def _fixed_engine(path):
    if path not in _fixed_engines:
        _fixed_engines[path] = _make_engine(path)
    return _fixed_engines[path]


def get_env_session():
    return Session(engine)


def get_novel_session():
    return Session(_fixed_engine(NOVEL_DB_PATH))


def get_test_session():
    return Session(_fixed_engine(TEST_DB_PATH))

