
from db.schema import *
from ai.local_ai.local_ai_time_keeper import loop_time
from tool.danger import reset_world


def redrive_world():
    reset_world.reset_world()

    loop_time(Stamp(2025))


if __name__ == "__main__":
    redrive_world()
