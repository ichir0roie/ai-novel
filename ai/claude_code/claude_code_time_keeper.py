#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code import ai_client
from db.schema import Session, Stamp
from ai.time_keeper import main as _main


def loop_time(start_time: Stamp | None = None, max_days: int | None = None) -> Stamp:
    try:
        return _main.loop_time(ai_client, start_time, max_days)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def time_process(s: Session, time: Stamp):
    return _main.time_process(s, time, ai_client)


def claude_main(year: int | None = None, max_days: int | None = None) -> Stamp:
    return loop_time(Stamp(year) if year is not None else None, max_days)


def loop_time_for_story(story_id: int, years: int = 5) -> Stamp:
    try:
        return _main.loop_time_for_story(ai_client, story_id, years)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def claude_story_years_main(story_id: int, years: int = 5) -> Stamp:
    return loop_time_for_story(story_id, years)


def daily_event(character_id: int | None = None) -> int | None:
    try:
        return _main.daily_event(ai_client, character_id)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def claude_daily_event_main(character_id: int | None = None) -> int | None:
    return daily_event(character_id)


if __name__ == "__main__":
    year = int(input("year>>"))
    loop_time(Stamp(year))
