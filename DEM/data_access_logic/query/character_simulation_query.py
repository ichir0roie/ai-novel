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
    time: Stamp,
    reach: int = 60,
) -> tuple[Sequence[Character], Sequence[Object], Sequence[Event]]:

    character_location_ids = (
        select(
            CharacterPlace.location_id
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
            CharacterPlace.location_id.in_(location_ids),
            __character_time_condition(time),
        ))
    ).all()
    objects = s.scalars(
        select(
            Object
        )
        .join(
            ObjectPlace, and_(
                ObjectPlace.object_id == Object.id,
                ObjectPlace.location_id.in_(location_ids),
                __object_time_condition(time),
            )
        )
    ).all()

    since = Stamp(max(1, time.year - reach))
    events = s.scalars(
        select(Event)
        .options(
            selectinload(Event.place),
            selectinload(Event.character),
            selectinload(Event.object),
        )
        .where(
            Event.place_id.in_(location_ids),
            Event.time <= time,
            Event.time >= since,
        )
        .order_by(Event.time.desc(), Event.id.desc())
    ).all()

    return characters, objects, events
