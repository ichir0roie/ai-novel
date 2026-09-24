
import shutil

from DEM.tool.markdown import export_db, import_db
WORLDS_ROOT = "world/worlds"


def run():
    import_db.import_db()
    export_db.export_db()


if __name__ == "__main__":
    run()
