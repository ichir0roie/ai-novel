from typing import Sequence
from DEM.db.schema import *
from DEM.data_access_logic.query import common_query


def location_time_condition(time: Stamp):
    return and_(
        Location.start <= time,
        or_(
            Location.end > time,
            Location.end == None
        )
    )


def location_active_condition():
    return Location.active_random_generation.is_(True)


def character_time_condition(time: Stamp):
    return and_(
        CharacterPlace.start <= time,
        or_(
            CharacterPlace.end > time,
            CharacterPlace.end == None
        )
    )


def plot_time_condition(time: Stamp):
    return and_(
        Plot.start <= time,
        or_(Plot.end.is_(None), Plot.end > time),
    )


def character_plot_time_condition(time: Stamp):
    return and_(
        CharacterPlot.start <= time,
        or_(CharacterPlot.end.is_(None), CharacterPlot.end > time),
    )
