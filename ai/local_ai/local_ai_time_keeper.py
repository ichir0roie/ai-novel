#!/usr/bin/env python3
from __future__ import annotations

from db.schema import Session, Stamp
from ai.local_ai import ai_client
from ai.time_keeper import main


def loop_time(start_time: Stamp | None = None, max_days: int | None = None) -> Stamp:
    return main.loop_time(ai_client, start_time, max_days)


def time_process(s: Session, time: Stamp):
    return main.time_process(s, time, ai_client)


def loop_time_for_story(story_id: int, years: int = 5) -> Stamp:
    return main.loop_time_for_story(ai_client, story_id, years)


def daily_event(character_id: int | None = None, age: int | None = None) -> int | None:
    return main.daily_event(ai_client, character_id, age)


if __name__ == "__main__":
    year = int(input("year>>"))
    stamp = Stamp(
        year
    )

    loop_time(stamp)
