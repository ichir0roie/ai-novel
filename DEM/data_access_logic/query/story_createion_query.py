from DEM.data_access_logic.query.base import *


def load_location_plot(
    s: Session,
    location_id: int,
    time: Stamp
):
    location_ids = []
    check_location = s.scalar(
        select(Location).where(Location.id == location_id)
    )
    if check_location is None:
        raise ValueError()

    location_ids.append(check_location.id)
    while True:
        next_location = s.scalar(
            select(Location).where(Location.id == check_location.parent_id)
        )
        if next_location is None:
            break
        location_ids.append(next_location.id)
        if next_location.parent_id is None:
            break

        check_location = next_location

    plots = s.scalars(
        select(
            Plot
        )
        .where(
            or_(Plot.location_id.in_(location_ids), Plot.location_id.is_(None)),
            plot_time_condition(time),
        )
    ).all()
    return plots
