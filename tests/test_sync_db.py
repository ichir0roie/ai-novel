import os
import time

import pytest

from ai.claude_code.interface.sync.export_db import ExportDb, ExportError
from ai.claude_code.interface.sync.import_db import ImportDb
from ai.claude_code.interface.sync.sync_db import SyncDb
from tool.markdown.import_db import ImportDbError
from db.schema import Character, CharacterParameter, CharacterPlace, Location
from tool.markdown import sync_manifest


@pytest.fixture
def root(session, tmp_path):
    session.add(Location(id=1, name="ヴァレンツァ", kind="街", text="石畳の街"))
    session.add(Location(id=2, name="ロザリオ", kind="村", text="丘の村"))
    session.commit()
    return str(tmp_path / "worlds")


def _md(root, name="1_ヴァレンツァ.md"):
    return os.path.join(root, "location", name)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _hand_edit(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _edit_db(session, row_id, **values):
    row = session.get(Location, row_id)
    for key, value in values.items():
        setattr(row, key, value)
    session.commit()


HAND = "# data\n```json\n{\"name\": \"ヴァレンツァ\", \"kind\": \"街\"}\n```\n\n# text\n手で直した\n"


def test_export_writes_manifest_and_skips_unchanged_files(root):
    ExportDb(root).run()
    assert os.path.exists(sync_manifest.manifest_path(root))
    before = os.stat(_md(root)).st_mtime_ns

    result = SyncDb(root).run()
    assert result == {"imported": {}, "deleted": [], "conflicts": [], "written": [], "removed": []}
    assert os.stat(_md(root)).st_mtime_ns == before


def test_sync_keeps_db_only_change(session, root):
    ExportDb(root).run()
    _edit_db(session, 1, text="db だけで直した")

    result = SyncDb(root).run()
    assert result["imported"] == {}
    assert result["written"] == ["location/1_ヴァレンツァ.md"]
    session.expire_all()
    assert session.get(Location, 1).text == "db だけで直した"
    assert "db だけで直した" in _read(_md(root))


def test_sync_takes_hand_edit_and_keeps_db_change_on_other_row(session, root):
    ExportDb(root).run()
    _hand_edit(_md(root), HAND)
    _edit_db(session, 2, text="別のセッションが直した")

    result = SyncDb(root).run()
    assert result["imported"] == {"location": 1}
    assert result["conflicts"] == []
    session.expire_all()
    assert session.get(Location, 1).text == "手で直した"
    assert session.get(Location, 2).text == "別のセッションが直した"
    assert "別のセッションが直した" in _read(_md(root, "2_ロザリオ.md"))


def test_hand_edit_wins_when_both_changed(session, root):
    ExportDb(root).run()
    _hand_edit(_md(root), HAND)
    _edit_db(session, 1, text="db でも直した")

    result = SyncDb(root).run()
    assert result["conflicts"] == ["location/1_ヴァレンツァ.md"]
    session.expire_all()
    assert session.get(Location, 1).text == "手で直した"


def test_row_deleted_in_db_removes_markdown(session, root):
    ExportDb(root).run()
    session.delete(session.get(Location, 2))
    session.commit()

    result = SyncDb(root).run()
    assert result["removed"] == ["location/2_ロザリオ.md"]
    assert not os.path.exists(_md(root, "2_ロザリオ.md"))
    session.expire_all()
    assert session.get(Location, 2) is None


def test_markdown_deleted_by_hand_deletes_row(session, root):
    ExportDb(root).run()
    os.remove(_md(root, "2_ロザリオ.md"))

    result = SyncDb(root).run()
    assert result["deleted"] == ["location/2_ロザリオ.md"]
    assert result["conflicts"] == []
    assert result["written"] == []
    assert not os.path.exists(_md(root, "2_ロザリオ.md"))
    session.expire_all()
    assert session.get(Location, 2) is None
    assert session.get(Location, 1) is not None
    assert SyncDb(root).run()["deleted"] == []


def test_markdown_deleted_by_hand_wins_over_db_change(session, root):
    ExportDb(root).run()
    os.remove(_md(root, "2_ロザリオ.md"))
    _edit_db(session, 2, text="db で直した")

    result = SyncDb(root).run()
    assert result["deleted"] == ["location/2_ロザリオ.md"]
    assert result["conflicts"] == ["location/2_ロザリオ.md"]
    session.expire_all()
    assert session.get(Location, 2) is None


def test_moved_markdown_does_not_delete_row(session, root):
    ExportDb(root).run()
    os.replace(_md(root), _md(root, "1_改名.md"))

    result = SyncDb(root).run()
    assert result["deleted"] == []
    session.expire_all()
    assert session.get(Location, 1).filename == "改名"


def test_deleted_markdown_takes_rows_not_in_markdown_along(session, root):
    session.add(Character(id=1, name="ノア", text=""))
    session.add(CharacterParameter(character_id=1, sex="女"))
    session.add(CharacterPlace(character_id=1, location_id=1))
    session.commit()
    ExportDb(root).run()
    os.remove(os.path.join(root, "character", "1_ノア.md"))

    assert SyncDb(root).run()["deleted"] == ["character/1_ノア.md"]
    session.expire_all()
    assert session.get(Character, 1) is None
    assert session.query(CharacterParameter).count() == 0
    assert session.query(CharacterPlace).count() == 0


def test_deleted_markdown_still_referred_stops_sync(session, root):
    session.add(Location(id=3, name="広場", kind="広場", text="", parent_id=2))
    session.commit()
    ExportDb(root).run()
    os.remove(_md(root, "2_ロザリオ.md"))

    with pytest.raises(ImportDbError):
        SyncDb(root).run()
    session.expire_all()
    assert session.get(Location, 2) is not None

    os.remove(_md(root, "3_広場.md"))
    assert SyncDb(root).run()["deleted"] == ["location/2_ロザリオ.md", "location/3_広場.md"]


def test_export_stops_when_markdown_deleted_by_hand(root):
    ExportDb(root).run()
    os.remove(_md(root))

    with pytest.raises(ExportError):
        ExportDb(root).run()
    assert not os.path.exists(_md(root))


def test_rename_in_db_moves_markdown(session, root):
    ExportDb(root).run()
    _edit_db(session, 1, name="新ヴァレンツァ")

    result = SyncDb(root).run()
    assert result["written"] == ["location/1_新ヴァレンツァ.md"]
    assert result["removed"] == ["location/1_ヴァレンツァ.md"]


def test_new_hand_written_markdown_gets_id(session, root):
    ExportDb(root).run()
    _hand_edit(_md(root, "新しい村.md"), "# data\n```json\n{\"kind\": \"村\"}\n```\n\n# text\n本文\n")

    result = SyncDb(root).run()
    assert result["imported"] == {"location": 1}
    row = session.query(Location).filter_by(filename="新しい村").one()
    assert os.path.exists(_md(root, f"{row.id}_新しい村.md"))
    assert not os.path.exists(_md(root, "新しい村.md"))
    assert SyncDb(root).run()["written"] == []


def test_without_manifest_only_markdown_differing_from_db_is_imported(session, root):
    ExportDb(root).run()
    os.remove(sync_manifest.manifest_path(root))
    _hand_edit(_md(root), HAND)

    result = SyncDb(root).run()
    assert result["imported"] == {"location": 1}
    assert result["written"] == ["location/1_ヴァレンツァ.md"]
    session.expire_all()
    assert session.get(Location, 1).text == "手で直した"
    assert SyncDb(root).run()["imported"] == {}


def test_moved_markdown_with_same_content_is_imported(session, root):
    ExportDb(root).run()
    moved = os.path.join(root, "location", "奥", "1_ヴァレンツァ.md")
    os.makedirs(os.path.dirname(moved))
    os.replace(_md(root), moved)

    assert SyncDb(root).run()["imported"] == {"location": 1}
    session.expire_all()
    assert session.get(Location, 1).directory_path == "奥"
    assert os.path.exists(moved)


def test_export_stops_when_markdown_edited_by_hand(root):
    ExportDb(root).run()
    _hand_edit(_md(root), HAND)

    with pytest.raises(ExportError) as raised:
        ExportDb(root).run()
    assert os.path.normpath(_md(root)) in str(raised.value)
    assert "手で直した" in _read(_md(root))


def test_import_lets_the_next_export_through(session, root):
    ExportDb(root).run()
    _hand_edit(_md(root), HAND)

    assert ImportDb(root).run() == {"location": 1}
    session.expire_all()
    assert session.get(Location, 1).text == "手で直した"

    ExportDb(root).run()
    assert "手で直した" in _read(_md(root))


def test_force_discards_hand_edits(root):
    ExportDb(root).run()
    _hand_edit(_md(root), HAND)

    ExportDb(root, force=True).run()
    assert "石畳の街" in _read(_md(root))


def test_lock_waits_for_other_sync(root):
    with sync_manifest.locked(root):
        with pytest.raises(sync_manifest.SyncLockedError):
            with sync_manifest.locked(root, timeout=0.1):
                pass
    with sync_manifest.locked(root, timeout=0.1):
        pass


def test_stale_lock_is_discarded(root):
    path = os.path.join(os.path.dirname(root), sync_manifest.LOCK_NAME)
    _hand_edit(path, "0\n")
    old = time.time() - sync_manifest.LOCK_STALE_SECONDS - 1
    os.utime(path, (old, old))

    with sync_manifest.locked(root, timeout=0.1):
        pass
    assert not os.path.exists(path)
