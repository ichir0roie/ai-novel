from DEM.data_access_logic.query.base import *


def load_location_plot(s: Session, location_id: int, time: Stamp):
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
        select(Plot).where(Plot.location_id.in_(location_ids), plot_time_condition(time))
    ).all()
