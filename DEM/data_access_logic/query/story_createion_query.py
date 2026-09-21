from DEM.data_access_logic.query.base import *


def load_location_plot(s: Session, location_id: int, time: Stamp):
    """その場所・祖先に紐づく筋書きに加え、`location_id` を問わない(場所を問わず全体に効く)筋書きも拾う。"""
    location = s.get(Location, location_id)
    if location is None:
        raise ValueError()

    location_ids = [location.id]
    while location.parent_id is not None:
        location = s.get(Location, location.parent_id)
        if location is None:
            break
        location_ids.append(location.id)

    return s.scalars(
        select(Plot).where(
            or_(Plot.location_id.in_(location_ids), Plot.location_id.is_(None)),
            plot_time_condition(time),
        )
    ).all()


def load_character_plot(s: Session, character_id: int, time: Stamp):
    return s.scalars(
        select(CharacterPlot).where(
            CharacterPlot.character_id == character_id,
            character_plot_time_condition(time),
        )
    ).all()
