from DEM.data_access_logic.query.base import *


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
            character_time_condition(time)
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
            character_time_condition(time),
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
                object_time_condition(time),
            )
        )
    ).all()

    since = Stamp(max(1, time.year - reach))
    events = s.scalars(
        select(Event)
        .options(*common_query.EVENT_LOAD_OPTIONS)
        .where(
            Event.place_id.in_(location_ids),
            Event.time <= time,
            Event.time >= since,
        )
        .order_by(Event.time.desc(), Event.id.desc())
    ).all()

    return characters, objects, events
