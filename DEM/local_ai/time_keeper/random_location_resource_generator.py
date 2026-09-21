#!/usr/bin/env python3
"""場所に紐づく資源を、時の流れの中で自動的に増やす。場所が生まれた直後と、資源が尽きた年初に一件作り db へ確定する。"""
from __future__ import annotations

from DEM.data_access_logic.query import world_createion_query
from DEM.db.schema import Location, LocationResource, Session, Stamp
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper._format import format_time
from DEM.randomizer.random_location_resource_generator import (
    build_location_resource,
)

_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "場所の名前・種別・環境を渡すので、そこにある資源を1件だけ考えてください。"
    "JSON で答えてください。キーは kind(資源の種別。木材/鉱石/水などの一言)、"
    "quantity(総量。100〜100000の整数)、unit(単位。一言)、"
    "years(この量が尽きるまでの年数。1〜500の整数)、"
    "text(一言で分かる説明)の五つだけ。"
)

_DEFAULT_YEARS = 50
_DEFAULT_QUANTITY = 1000


def _should_roll(time: Stamp) -> bool:
    """年に一度、年初(1月1日)にだけ見る。"""
    return time.month == 1 and time.day == 1


def _end_after_years(start: Stamp, years: int) -> Stamp:
    return Stamp(start.year + max(years, 1), start.month, start.day,
                 start.hour, start.minute, start.second)


def _create_resource(
    session: Session, location: Location, time: Stamp
) -> LocationResource:
    prompt = (
        f"場所: {location.name}(id={location.id}, 種別={location.kind}, "
        f"環境={location.environment or '-'})\n"
        f"現在の時刻: {time}\n"
        "この場所にある資源を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(prompt, system=_SYSTEM_PROMPT)

    draft = build_location_resource(
        location_id=location.id,
        kind=decided.get("kind") or "資源",
        quantity=int(decided.get("quantity") or _DEFAULT_QUANTITY),
        unit=decided.get("unit") or "単位",
        text=decided.get("text") or "",
        start=time,
        end=_end_after_years(time, int(decided.get("years") or _DEFAULT_YEARS)),
    )
    record = LocationResource(**draft)
    session.add(record)
    session.commit()
    when = format_time(time)
    print(f"[time_keepr/location_resource] {when} 生成: "
          f"{location.name}(id={location.id}) に {record.kind} "
          f"{record.quantity}{record.unit}"
          f"({when}〜{format_time(record.end)})")
    return record


def generate_for_new_location(
    session: Session, location: Location, time: Stamp
) -> LocationResource:
    """場所が生まれた直後に、その場所の初めの資源を一件作る。"""
    return _create_resource(session, location, time)


def generate_random(session: Session, time: Stamp) -> list[LocationResource]:
    """年初に、前の資源が尽きた場所へ、次の資源を一件ずつ足す。"""
    if not _should_roll(time):
        return []

    depleted = session.scalars(
        world_createion_query.locations_without_current_resource_select(time)
    ).all()
    return [_create_resource(session, location, time) for location in depleted]
