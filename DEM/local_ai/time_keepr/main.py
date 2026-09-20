
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
    event_progression_generator,
    random_character_generator,
    random_location_generator,
    random_location_resource_generator,
    # random_object_generator
)
from DEM.local_ai.time_keepr._format import format_time, next_day


def loop_time(start_time: Stamp | None = None):
    if start_time is None:
        with get_session() as s:
            start_time = s.scalar(
                common_query.latest_time_select()
            ) or Stamp(1)
    current_time = start_time

    while True:
        print(f"[time_keepr] {format_time(current_time)}")
        with get_session() as s:
            time_process(s, current_time)

        current_time = next_day(current_time)


def time_process(
    s: Session, time: Stamp
):

    random_location_generator.generate_random(s, time)
    random_location_resource_generator.generate_random(s, time)
    random_character_generator.generate_random(s, time)
    event_progression_generator.generate_random(s, time)
    # random_object_generator.generate_random(s, time)


if __name__ == "__main__":
    year = int(input("year>>"))
    stamp = Stamp(
        year
    )

    loop_time(stamp)
