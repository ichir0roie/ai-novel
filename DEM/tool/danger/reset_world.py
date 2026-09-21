
from DEM.db.schema import *


delete_tables = [
    Event,
    EventCharacter,
    EventObject,
    Object,
    ObjectPlace,
    Character,
    CharacterPlace,
    CharacterDrive,
    CharacterPlot,
]


def reset_world():

    with get_session() as s:
        for t in delete_tables:
            s.execute(delete(t))
        s.commit()


if __name__ == "__main__":
    reset_world()
