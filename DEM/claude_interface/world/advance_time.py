#!/usr/bin/env python3
"""世界の側を1日ぶん進めるのに要る材料を出す、claude が呼ぶ入口。

`DEM/local_ai/time_keeper/` の常駐ループ(ローカル AI が生成を担当し、db に
直接書き込む)とは別の経路。**生成そのものは呼び出す側(claude)が行い、
書き込みは他の `DEM/claude_interface/randomizer/` の入口を通す。** ここは
「いつ・どこで・何を決めればよいか」という下ごしらえ(確率のロール・
候補地の絞り込み・文脈の取り出し)だけを担い、db には一切書き込まない
(`local_ai` は import しない)。

内容を決める前に、`IHG/naming.md` `IHG/writing-style.md` `IHG/principles.md`
`IHG/chronicle.md`(出来事の書き方)を読むこと。

使い方。1日ぶん、`kind` をこの順で呼ぶ(前の kind の確定が同じ日の次の
kind の候補に響くので、崩さないこと)::

    AdvanceTime(kind="character", time="4360/03/01").run()
    # 材料があれば、CreateRandomCharacter で下書きを作り、name/read/text/
    # start(=年初-年齢)を上書きして CommitCharacter で確定し、続けて
    # CommitCharacterDrive・CommitCharacterPlot を呼ぶ
    AdvanceTime(kind="object", time="4360/03/01").run()
    AdvanceTime(kind="lifespan", time="4360/03/01").run()
    AdvanceTime(kind="event", time="4360/03/01").run()
    # 次の日へ。next_time は結果に必ず入っている
    AdvanceTime(kind="character", time=result["next_time"]).run()

`time` を省くと db の最新時刻から始める。`active_plots` が 0 なら
`stopped: true` を立てて、`CommitPlot` で筋書きを足すまで進めない
(`time_keeper.loop_time` と同じ止まり方)。`needs` が空・None ならその
kind は何もしなくてよい(ロールが外れた)。
"""
from __future__ import annotations

import random

from DEM.claude_interface._base import SessionEntrypoint
from DEM.data_access_logic.query import (
    common_query, story_createion_query, world_createion_query,
)
from DEM.db.schema import Location, Session, Stamp

# --- 時刻を進める(ローカル AI も db 書き込みも介さない、純粋な計算) --------
#
# `DEM/local_ai/time_keeper/_format.next_day` と同じ刻み方(1〜60日の
# ランダムな跳躍。月をまたぐと必ず1日に着地するので、月初判定のロールを
# 取りこぼさない)。処理の流れを比べやすいよう、ここでも同じ刻み方にする。

_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _next_time(time: Stamp) -> Stamp:
    year, month, day = time.year, time.month, time.day
    days_in_month = _MONTH_DAYS[month - 1]
    if month == 2 and _is_leap_year(year):
        days_in_month = 29
    day += random.randint(1, 60)
    if day > days_in_month:
        day = 1
        month += 1
        if month > 12:
            month = 1
            year += 1
    return Stamp(year, month, day, time.hour, time.minute, time.second)


# --- 生成の確率・条件。`DEM/local_ai/time_keeper/` の各生成器と同じ値 -------

_CHARACTER_PROBABILITY = 0.25    # random_character_generator と同じ
_OBJECT_PROBABILITY = 0.15       # random_object_generator と同じ
_EVENT_PLACE_PROBABILITY = 0.30  # event_progression_generator と同じ
_AGE_RANGE = (0, 40)
_NATURAL_DEATH_MIN_AGE = 50
_NATURAL_DEATH_MAX_AGE = 150
_ACCIDENT_PROBABILITY_PER_YEAR = 0.003
_REACH_LEVELS = 1
_REACH_OBJECT_LIMIT = 10


def _natural_death_probability(age: int) -> float:
    if age < _NATURAL_DEATH_MIN_AGE:
        return 0.0
    if age >= _NATURAL_DEATH_MAX_AGE:
        return 1.0
    span = _NATURAL_DEATH_MAX_AGE - _NATURAL_DEATH_MIN_AGE
    return (age - _NATURAL_DEATH_MIN_AGE) / span


def _place_brief(place: Location | None) -> dict | None:
    if place is None:
        return None
    return {
        "id": place.id, "name": place.name, "kind": place.kind,
        "text": place.text, "sample_region": place.sample_region,
        "sample_culture": place.sample_culture, "sample_era": place.sample_era,
    }


def _region_label(session: Session, place: Location | None) -> str | None:
    if place is None or place.parent_id is None:
        return None
    parent = session.get(Location, place.parent_id)
    return f"{parent.name}({parent.kind})" if parent else None


def _plot_texts(session: Session, place: Location | None, time: Stamp) -> list[str]:
    if place is None:
        return []
    plots = story_createion_query.load_location_plot(session, place.id, time)
    return [p.text for p in plots if p.text]


class AdvanceTime(SessionEntrypoint):
    """`kind` は `character` `object` `lifespan` `event` のどれか一つ。"""

    def __init__(self, kind: str, time: str | None = None):
        if kind not in ("character", "object", "lifespan", "event"):
            raise ValueError(
                f"kind={kind!r} は character/object/lifespan/event のどれかで渡す")
        self.kind = kind
        self.time = time

    def execute(self, session: Session) -> dict:
        time = Stamp.parse(self.time) if self.time else (
            session.scalar(common_query.latest_time_select()) or Stamp(1))
        result = {
            "time": str(time), "kind": self.kind,
            "next_time": str(_next_time(time)),
        }

        active = int(session.scalar(
            world_createion_query.active_plot_count_select(time)) or 0)
        result["active_plots"] = active
        if not active:
            result["stopped"] = True
            result["message"] = (
                f"{result['time']} をカバーするプロットが無い。"
                "CommitPlot で筋書きを足すまで進められない")
            result["needs"] = None
            return result
        result["stopped"] = False

        method = getattr(self, f"_{self.kind}_needs")
        result["needs"] = method(session, time)
        return result

    # --- 人物 ------------------------------------------------------------

    def _character_needs(self, session: Session, time: Stamp) -> dict | None:
        """月初(day==1)に確率 `_CHARACTER_PROBABILITY` で場所を一つ選ぶ。"""
        if time.day != 1:
            return None
        if random.random() >= _CHARACTER_PROBABILITY:
            return None

        places = session.scalars(world_createion_query.alive_locations_select(time)).all()
        eligible = [
            p for p in places
            if int(session.scalar(
                world_createion_query.character_count_at_place_select(p.id, time)) or 0)
            < world_createion_query.MAX_PER_LOCATION
            and world_createion_query.location_has_plot(session, p.id)
        ]
        if places and not eligible:
            return None
        place = random.choice(eligible) if eligible else None

        return {
            "place": _place_brief(place),
            "region": _region_label(session, place),
            "plots": _plot_texts(session, place, time),
            "age_range": list(_AGE_RANGE),
            "instruction": (
                "この場所(無ければ場所不定)に自然な人物を1件決める。"
                "IHG/naming.md の人名の基準に沿って name/read を決め、text に"
                "具体的な生活・仕事・関係(固有の癖・関わり・生い立ちを"
                "最低一つ)を書く。age は age_range の範囲で text と矛盾しない"
                "歳を選ぶ。情動(信念・目標・意図)と、その人物専用の筋書き"
                "(今後どう動くか、1〜2文)も決める。"
                "CreateRandomCharacter で下書きを作り、name/read/text/start"
                "(=time.year - age を年とした Stamp)を上書きしてから "
                "CommitCharacter({..., place_id})で確定し、続けて "
                "CommitCharacterDrive({character_id, text, level, start: time})、"
                "CommitCharacterPlot({character_id, text, start: time}) を呼ぶ。"
            ),
        }

    # --- 個体 ------------------------------------------------------------

    def _object_needs(self, session: Session, time: Stamp) -> dict | None:
        """月初に確率 `_OBJECT_PROBABILITY` で、人物が居てプロットのある場所を選ぶ。"""
        if time.day != 1:
            return None
        if random.random() >= _OBJECT_PROBABILITY:
            return None

        places = session.scalars(world_createion_query.alive_locations_select(time)).all()
        eligible = [
            p for p in places
            if int(session.scalar(
                world_createion_query.character_count_at_place_select(p.id, time)) or 0) > 0
            and int(session.scalar(
                world_createion_query.object_count_at_place_select(p.id, time)) or 0)
            < world_createion_query.MAX_PER_LOCATION
            and world_createion_query.location_has_plot(session, p.id)
        ]
        if not eligible:
            return None
        place = random.choice(eligible)

        resident_character_ids = set(session.scalars(
            common_query.resident_character_ids_select([place.id], time)).all())
        resident_object_ids = set(session.scalars(
            common_query.resident_object_ids_select([place.id], time)).all())
        characters = [
            c for c in session.scalars(world_createion_query.alive_characters_select(time)).all()
            if c.id in resident_character_ids
        ]
        objects = [
            o for o in session.scalars(world_createion_query.alive_objects_select(time)).all()
            if o.id in resident_object_ids
        ]

        return {
            "place": _place_brief(place),
            "characters": [{"id": c.id, "name": c.name, "text": c.text} for c in characters[:10]],
            "objects": [{"id": o.id, "name": o.name, "text": o.text} for o in objects[:10]],
            "plots": _plot_texts(session, place, time),
            "scale_options": {"集落内": 0, "地域": 1, "国": 2, "大陸": 3},
            "instruction": (
                "この場所を拠り所に生まれる群(国・組織・商会・氏族・徒党など、"
                "まとまりとして動くもの)を1件決める。IHG/naming.md の用語の"
                "基準に沿って name/read を決め、text にこの群が何であって・"
                "何を決められて・誰に対して力を持つのかを、場所の産業・地形・"
                "人間関係を具体的に使って書く。既にある群と役割を重ねない。"
                "CreateRandomObject で下書きを作り、name/read/text/place_id/"
                "start(=time)/world_influence(scale_options の対応する値)を"
                "上書きして CommitObject で確定する。"
            ),
        }

    # --- 寿命 ------------------------------------------------------------

    def _lifespan_needs(self, session: Session, time: Stamp) -> list[dict]:
        """年初(1月1日)に、生きている人物それぞれの老衰・事故をロールする。

        **誰がいつ死ぬかはここで決まる(乱数)。** 死の記録(名前・本文)だけを
        呼び出す側が決めて、`UpdateCharacter` で `end` を立て、`CommitEvent`
        で記録する。
        """
        if not (time.month == 1 and time.day == 1):
            return []

        needs = []
        characters = session.scalars(world_createion_query.alive_characters_select(time)).all()
        for character in characters:
            if character.start is None:
                continue
            age = time.year - character.start.year

            if _NATURAL_DEATH_MAX_AGE < age:
                dead_age = random.randint(_NATURAL_DEATH_MAX_AGE, age)
                dead_time = Stamp(character.start.year + dead_age)
                needs.append(self._death_need(session, character, dead_time, "老衰", dead_age))
                continue

            if random.random() < _natural_death_probability(age):
                needs.append(self._death_need(session, character, time, "老衰", age))
                continue

            if random.random() < _ACCIDENT_PROBABILITY_PER_YEAR:
                needs.append(self._death_need(session, character, time, "事故", age))

        return needs

    @staticmethod
    def _death_need(session: Session, character, time: Stamp, cause: str, age: int) -> dict:
        place = session.scalars(
            common_query.character_place_select(character.id, time)).first()
        return {
            "character": {"id": character.id, "name": character.name, "text": character.text},
            "cause": cause,
            "age": age,
            "time": str(time),
            "location_id": place.location_id if place else None,
            "instruction": (
                f"{character.name}(id={character.id})の最期を1件決める"
                f"(死因: {cause})。event_name・event_text を決めたら、"
                "UpdateCharacter({id, end: time}) で end を立ててから、"
                "CommitEvent({name, text, time, location_id, start: time, "
                "end: time, character_ids: [id]}) で記録する。"
            ),
        }

    # --- 出来事 ----------------------------------------------------------

    def _event_needs(self, session: Session, time: Stamp) -> list[dict]:
        """月初に、人物・個体が居る場所それぞれについて出来事をロールする。"""
        if time.day != 1:
            return []

        grouped = self._group_by_place(session, time)
        needs = []
        for place_id, (characters, objects) in grouped.items():
            if random.random() >= _EVENT_PLACE_PROBABILITY:
                continue
            reach_objects = self._reach_objects(
                session, grouped, place_id, {o.id for o in objects})
            needs.append(
                self._event_need(session, place_id, characters, objects, reach_objects, time))
        return needs

    @staticmethod
    def _group_by_place(session: Session, time: Stamp) -> dict[int, tuple[list, list]]:
        """`event_progression_generator._group_by_place` と同じ絞り込み。"""
        grouped: dict[int, tuple[list, list]] = {}

        def bucket(place_id):
            return grouped.setdefault(place_id, ([], []))

        busy_character_ids = set(session.scalars(
            world_createion_query.busy_character_ids_select(time)).all())
        for character in session.scalars(world_createion_query.alive_characters_select(time)).all():
            if character.id in busy_character_ids:
                continue
            place = session.scalars(
                common_query.character_place_select(character.id, time)).first()
            if place is None:
                continue
            bucket(place.location_id)[0].append(character)

        for obj in session.scalars(world_createion_query.alive_objects_select(time)).all():
            place = session.scalars(
                common_query.object_place_select(obj.id, time)).first()
            if place is None:
                continue
            bucket(place.location_id)[1].append(obj)

        return grouped

    @staticmethod
    def _reach_objects(session: Session, grouped, place_id: int, exclude_ids: set[int]) -> list:
        """一つ上の圏内から遠隔で関与できる個体の候補。"""
        root_id = common_query.place_up(session, place_id, _REACH_LEVELS)
        nearby_ids = common_query.descendant_place_ids(session, root_id)
        found = []
        seen = set(exclude_ids)
        for nearby_id in nearby_ids:
            if nearby_id == place_id:
                continue
            for obj in grouped.get(nearby_id, ([], []))[1]:
                if obj.id in seen:
                    continue
                seen.add(obj.id)
                found.append(obj)
                if len(found) >= _REACH_OBJECT_LIMIT:
                    return found
        return found

    @staticmethod
    def _event_need(
        session: Session, place_id: int, characters: list, objects: list,
        reach_objects: list, time: Stamp,
    ) -> dict:
        place = session.get(Location, place_id)
        recent_events = session.scalars(
            common_query.events_of_select(place_id, until=time, limit=5)).all()
        plots = story_createion_query.load_location_plot(session, place_id, time)
        character_plots = {
            c.id: [p.text for p in story_createion_query.load_character_plot(session, c.id, time)]
            for c in characters[:20]
        }
        return {
            "place": _place_brief(place),
            "characters": [
                {"id": c.id, "name": c.name, "tone": c.tone, "text": c.text,
                 "plot": character_plots.get(c.id) or []}
                for c in characters[:20]
            ],
            "objects": [
                {"id": o.id, "name": o.name, "text": o.text, "world_influence": o.world_influence}
                for o in objects[:20]
            ],
            "reach_objects": [
                {"id": o.id, "name": o.name, "text": o.text, "world_influence": o.world_influence}
                for o in reach_objects
            ],
            "recent_events": [{"id": e.id, "name": e.name} for e in recent_events],
            "plots": [p.text for p in plots],
            "time": str(time),
            "instruction": (
                "居合わせる人物・個体・場所のうち、どれとどれが噛み合ってこの"
                "出来事になったのかを踏まえて1件決める(IHG/chronicle.md の"
                "出来事の書き方に沿う)。進めたい筋書き・人物の plot があれば"
                "そこへ向かう一歩を優先する。関わった人物は characters の id、"
                "個体は objects/reach_objects の id からだけ選ぶ。"
                "CommitEvent({name, text, time, location_id, start: time, "
                "end: 継続日数ぶん先の Stamp, character_ids, object_ids, "
                "character_drives?}) で記録する。人物の記述が変わったときだけ "
                "UpdateCharacter({id, text, belong_id?}) を、個体の記述が"
                "変わったときだけ UpdateObject({id, text}) を追加で呼ぶ。"
                "居合わせる個体にも遠隔の候補にもふさわしい主体が見当たらない"
                "ときだけ、CommitObject でこの場所に新しい個体を誕生させて"
                "よい。この出来事で場所自体が消滅するなら "
                "UpdatePlace({id: location_id, end: time})、新しい場所が"
                "生まれるなら CommitPlace({parent_id: location_id, ...}) を"
                "追加で呼ぶ。"
            ),
        }
