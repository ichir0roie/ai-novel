from DEM.data_access_logic.query.base import *


def load_location_plot(s: Session, location_id: int, time: Stamp):
    """`location_id` とその祖先に掛かる、`time` に有効な筋書き。上位の場所のものから順。"""
    location = s.get(Location, location_id)
    if location is None:
        raise ValueError()

    location_ids = [location.id]
    while location.parent_id is not None:
        location = s.get(Location, location.parent_id)
        if location is None:
            break
        location_ids.append(location.id)

    depth = {lid: i for i, lid in enumerate(reversed(location_ids))}
    plots = s.scalars(
        select(Plot).where(
            Plot.location_id.in_(location_ids),
            plot_time_condition(time),
        ).order_by(Plot.id)
    ).all()
    return sorted(plots, key=lambda p: depth[p.location_id])


def join_plot_text(plots: list[Plot]) -> str:
    """筋書きの本文を、渡された順のまま一つのテキストにつなげる。"""
    return "\n\n".join(p.text for p in plots if p.text)


def load_location_plot_text(s: Session, location_id: int, time: Stamp) -> str:
    return join_plot_text(load_location_plot(s, location_id, time))


def load_character_plot(s: Session, character_id: int, time: Stamp):
    return s.scalars(
        select(CharacterPlot).where(
            CharacterPlot.character_id == character_id,
            character_plot_time_condition(time),
        )
    ).all()
