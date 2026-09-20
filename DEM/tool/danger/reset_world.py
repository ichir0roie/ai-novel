
from DEM.db.schema import *


delete_tables = [
    LocationResource,
    Event,
    EventCharacter,
    EventObject,
    ObjectPlace,
    Character,
    CharacterPlace,
    CharacterDrive,
    CharacterSkill
]


def reset_world():

    with get_session() as s:
        for t in delete_tables:
            s.execute(delete(t))
        s.commit()


if __name__ == "__main__":
    reset_world()
