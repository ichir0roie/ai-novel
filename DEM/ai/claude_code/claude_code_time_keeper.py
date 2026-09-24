#!/usr/bin/env python3
"""常駐ループ(`DEM/ai/time_keeper/main.py`)を、Claude Code(`claude -p`)を生成に使って回す入口。

`claude_main` は、このループを claude code から起動するための非対話の入口。
"""
from __future__ import annotations

from DEM.ai.claude_code import ai_client
from DEM.db.schema import Session, Stamp
from DEM.ai.time_keeper import main as _main


def loop_time(start_time: Stamp | None = None, max_days: int | None = None) -> Stamp:
    """終わりに Claude Code の呼び出し回数とトークンを出す。"""
    try:
        return _main.loop_time(ai_client, start_time, max_days)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def time_process(s: Session, time: Stamp):
    return _main.time_process(s, time, ai_client)


def claude_main(year: int | None = None, max_days: int | None = None) -> Stamp:
    """`year` を省くと db の最新の時刻から続ける。`max_days` を渡すとその日数で区切る。"""
    return loop_time(Stamp(year) if year is not None else None, max_days)


def loop_time_for_story(story_id: int, years: int = 5) -> Stamp:
    """終わりに Claude Code の呼び出し回数とトークンを出す。"""
    try:
        return _main.loop_time_for_story(ai_client, story_id, years)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def claude_story_years_main(story_id: int, years: int = 5) -> Stamp:
    """作品 `story_id` の開始時刻から、`years` 年ぶん進める(既定 5 年)。"""
    return loop_time_for_story(story_id, years)


def daily_event() -> int | None:
    """終わりに Claude Code の呼び出し回数とトークンを出す。"""
    try:
        return _main.daily_event(ai_client)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def claude_daily_event_main() -> int | None:
    """サブキャラクター一人の次の出来事を一件起こす(毎日のルーチン)。起こした出来事の id を返す。"""
    return daily_event()


if __name__ == "__main__":
    year = int(input("year>>"))
    loop_time(Stamp(year))
