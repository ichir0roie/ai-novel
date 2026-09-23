from typing import Sequence
from DEM.db.schema import *
from DEM.data_access_logic.query import common_query


def location_time_condition(time: Stamp):
    return and_(
        or_(Location.start.is_(None), Location.start <= time),
        or_(
            Location.end > time,
            Location.end == None
        )
    )


def location_active_condition(time: Stamp):
    return and_(
        location_time_condition(time),
        Location.active_random_generation.is_(True)
    )


def character_active_condition():
    """人物・対象が出来事・筋書きのランダム生成の対象になるか。メインキャラクター(`sub_character` が false)は対象外。"""
    return Character.sub_character.is_(True)


def character_time_condition(time: Stamp):
    return and_(
        or_(CharacterPlace.start.is_(None), CharacterPlace.start <= time),
        or_(
            CharacterPlace.end > time,
            CharacterPlace.end == None
        )
    )


def plot_time_condition(time: Stamp):
    return and_(
        or_(Plot.start.is_(None), Plot.start <= time),
        or_(Plot.end.is_(None), Plot.end > time),
    )


def character_plot_time_condition(time: Stamp):
    return and_(
        or_(CharacterPlot.start.is_(None), CharacterPlot.start <= time),
        or_(CharacterPlot.end.is_(None), CharacterPlot.end > time),
    )
