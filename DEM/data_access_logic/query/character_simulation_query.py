from typing import Sequence
from DEM.db.schema import *


def __character_time_condition(time: Stamp):
    return or_(
        and_(
            CharacterPlace.start <= time,
            CharacterPlace.end > time,
        ),
        and_(
            CharacterPlace.start <= time,
            CharacterPlace.end == None
        )

    )


def __object_time_condition(time: Stamp):
    return or_(
        and_(
            ObjectPlace.start <= time,
            ObjectPlace.end > time
        ),
        and_(
            ObjectPlace.start <= time,
            ObjectPlace.end == None
        )
    )


def character_around_event(
    s: Session,
    character_id: int,
    time: Stamp
) -> tuple[Sequence[Character], Sequence[Object]]:

    character_location_ids = (
        select(
            CharacterPlace.id
        )
        .where(
            CharacterPlace.character_id == character_id,
            __character_time_condition(time)
        )
    )

    location_res = s.scalars(
        select(Location)
        .where(
            or_(
                Location.parent_id.in_(character_location_ids),
                Location.id.in_(character_location_ids)
            )
        )
        .options(
            selectinload(Location.children)
        )
    ).all()

    locations: list[Location] = []
    for location in location_res:
        locations.append(location)
        for child_location in location.children:
            locations.append(child_location)

    location_ids = [l.id for l in locations]

    characters = s.scalars(
        select(
            Character
        )
        .join(CharacterPlace, and_(
            CharacterPlace.character_id == Character.id,
            __character_time_condition(time)
        ))
    ).all()
    objects = s.scalars(
        select(
            Object
        )
        .join(
            ObjectPlace, and_(
                ObjectPlace.object_id == Object.id,
                __object_time_condition(time)
            )
        )
    ).all()

    return characters, objects
