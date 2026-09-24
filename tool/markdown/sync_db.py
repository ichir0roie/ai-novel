
import shutil

from tool.markdown import export_db, import_db
from db.schema import WORLDS_ROOT  # noqa: F401


def run():
    import_db.import_db()
    export_db.export_db()


if __name__ == "__main__":
    run()
