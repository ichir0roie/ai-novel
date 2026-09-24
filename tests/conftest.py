"""テストは `novel.test.db` だけを読み書きする。`DEM.tool.test` を最初に import して db パスを固定する。"""
import os

import pytest

from DEM.tool.test import TEST_DB_PATH  # noqa: F401  schema より先に読む(db を novel.test.db に固定)
from DEM.db.schema import Base, create_db, engine, get_env_session, get_test_session  # noqa: E402
from DEM.tool.markdown import export_db, import_db  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402


@event.listens_for(Engine, "connect")
def _fast_sqlite(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA synchronous=OFF")
    cursor.execute("PRAGMA journal_mode=MEMORY")
    cursor.close()


@pytest.fixture(scope="session", autouse=True)
def fresh_test_db():
    """セッションの最初に空の db ファイルを作り直す。以後は同じファイルを使い回す。"""
    # create_db が返す engine も捨てる。消して作り直したファイルを掴んだまま
    # 残ると、以後の書き込みが sqlite の disk I/O error になることがある
    create_db(TEST_DB_PATH).dispose()
    engine.dispose()  # 作り直す前のファイルを掴んでいる接続を捨てる
    yield


def _rebuild_tables():
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    Base.metadata.create_all(engine)


@pytest.fixture(autouse=True)
def clean_tables(request):
    """テストごとに行を消して、前のテストの行を残さない。表の張り直しより速い。"""
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield
    # old_style_db は表の形を旧版へ書き換えるので、あとのテストのために張り直す
    if "old_style_db" in request.fixturenames:
        engine.dispose()
        _rebuild_tables()


@pytest.fixture(autouse=True)
def sync_tools_use_test_db(monkeypatch):
    """`import_db` / `export_db` は novel.db 固定なので、テスト中だけ novel.test.db へ向ける。"""
    monkeypatch.setattr(export_db, "get_novel_session", get_test_session)
    monkeypatch.setattr(import_db, "get_novel_session", get_test_session)
    monkeypatch.setattr(import_db, "NOVEL_DB_PATH", TEST_DB_PATH)
    yield


@pytest.fixture
def session():
    with get_env_session() as s:
        yield s
