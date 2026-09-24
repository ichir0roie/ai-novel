import os

import pytest

from ai.claude_code.interface.sync.export_db import ExportDb, ExportError
from ai.claude_code.interface.sync.import_db import ImportDb
from db.schema import Location
from tool.markdown import sync_stamp


@pytest.fixture
def root(session, tmp_path):
    session.add(Location(id=1, name="ヴァレンツァ", kind="街", text="石畳の街"))
    session.commit()
    return str(tmp_path / "worlds")


def _md(root):
    return os.path.join(root, "location", "1_ヴァレンツァ.md")


def _hand_edit(root, text):
    """md を手で直す。印を一秒だけ戻して、md の方が後に書かれた形を確実にする。"""
    path = _md(root)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    earlier = os.stat(path).st_mtime_ns - 10 ** 9
    os.utime(sync_stamp.stamp_path(root), ns=(earlier, earlier))


def test_export_marks_synced_and_can_run_again(root):
    ExportDb(root).run()
    assert os.path.exists(sync_stamp.stamp_path(root))
    assert sync_stamp.edited_since_sync(root) == []
    assert ExportDb(root).run()["location"] == 1


def test_export_without_stamp_is_allowed(root):
    assert not os.path.exists(sync_stamp.stamp_path(root))
    assert ExportDb(root).run()["location"] == 1


def test_export_stops_when_markdown_edited_by_hand(root):
    ExportDb(root).run()
    _hand_edit(root, "# data\n```json\n{\"kind\": \"街\"}\n```\n\n# text\n手で直した\n")

    with pytest.raises(ExportError) as raised:
        ExportDb(root).run()
    assert _md(root) in str(raised.value)

    with open(_md(root), encoding="utf-8") as f:
        assert "手で直した" in f.read()


def test_import_lets_the_next_export_through(session, root):
    ExportDb(root).run()
    _hand_edit(root, "# data\n```json\n{\"kind\": \"街\"}\n```\n\n# text\n手で直した\n")

    ImportDb(root).run()
    session.expire_all()
    assert session.get(Location, 1).text == "手で直した"

    ExportDb(root).run()
    with open(_md(root), encoding="utf-8") as f:
        assert "手で直した" in f.read()


def test_force_discards_hand_edits(root):
    ExportDb(root).run()
    _hand_edit(root, "# data\n```json\n{\"kind\": \"街\"}\n```\n\n# text\n手で直した\n")

    ExportDb(root, force=True).run()
    with open(_md(root), encoding="utf-8") as f:
        assert "石畳の街" in f.read()
