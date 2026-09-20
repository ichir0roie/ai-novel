
from DEM.db.schema import *
from DEM.local_ai import ai_client
from DEM.data_access_logic.query import (
    character_simulation_query,
    common_query,
    dictionary_query,
    story_createion_query,
    world_createion_query
)
from DEM.local_ai.time_keepr import (
    random_character_generator,
    random_location_generator,
    # random_object_generator
)

# 月ごとの日数。うるう年（4で割れて、100で割れないか400で割れる）は2月を29日にする。
_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _next_day(time: Stamp) -> Stamp:
    """時刻を1日ぶん進める。"""
    year, month, day = time.year, time.month, time.day
    days_in_month = _MONTH_DAYS[month - 1]
    if month == 2 and _is_leap_year(year):
        days_in_month = 29

    day += 1
    if day > days_in_month:
        day = 1
        month += 1
        if month > 12:
            month = 1
            year += 1

    return Stamp(year, month, day, time.hour, time.minute, time.second)


def loop_time(start_time: Stamp | None = None):
    if start_time is None:
        with get_session() as s:
            start_time = s.scalar(
                common_query.latest_time_select()
            ) or Stamp(1)
    current_time = start_time

    while True:
        with get_session() as s:
            time_process(s, current_time)

        current_time = _next_day(current_time)


def time_process(
    s: Session, time: Stamp
):

    random_location_generator.generate_random(s, time)
    random_character_generator.generate_random(s, time)
    # random_object_generator.generate_random(s, time)


if __name__ == "__main__":
    year = int(input("year>>"))
    stamp = Stamp(
        year
    )

    loop_time(stamp)
