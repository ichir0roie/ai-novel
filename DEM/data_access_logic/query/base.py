from typing import Sequence
from DEM.db.schema import *
from DEM.data_access_logic.query import common_query


def character_time_condition(time: Stamp):
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


def object_time_condition(time: Stamp):
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


def plot_time_condition(time: Stamp):
    """`time` の時点でまだ有効な筋書き(`start`〜`end` が空なら期間を問わない)。"""
    return and_(
        or_(Plot.start.is_(None), Plot.start <= time),
        or_(Plot.end.is_(None), Plot.end > time),
    )


def character_plot_time_condition(time: Stamp):
    """`time` の時点でまだ有効な人物の筋書き(`start`〜`end` が空なら期間を問わない)。"""
    return and_(
        or_(CharacterPlot.start.is_(None), CharacterPlot.start <= time),
        or_(CharacterPlot.end.is_(None), CharacterPlot.end > time),
    )
