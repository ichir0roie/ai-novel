#!/usr/bin/env python3
from __future__ import annotations

import os

from db.schema import WORLDS_ROOT, get_novel_session
from tool.markdown import export_db, import_db
from tool.markdown.sync_manifest import Manifest, locked

__all__ = ["WORLDS_ROOT", "sync_db", "run"]


def sync_db(root: str = WORLDS_ROOT) -> dict:
    """手で直された md だけを db へ入れ、db と食い違う md だけを書き直す。

    いつ呼んでも、db にだけ入った変更も md にだけ入った変更も消さない。
    同じ行を両方で直していたら md(ユーザの直接編集)を勝たせ、`conflicts` に返す。
    """
    with locked(root):
        manifest = Manifest(root)
        with get_novel_session() as session:
            imported = import_db.import_changes(session, root, manifest)
            session.commit()
            exported = export_db.export_changes(session, root, manifest)
        manifest.save()

    def relative(paths):
        return [os.path.relpath(path, root).replace(os.sep, "/") for path in paths]

    return {
        "imported": imported["counts"],
        "conflicts": relative(imported["conflicts"]),
        "written": relative(exported["written"]),
        "removed": relative(exported["removed"]),
    }


def run():
    print(sync_db())


if __name__ == "__main__":
    run()
