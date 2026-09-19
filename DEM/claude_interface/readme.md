claudeが実行するスクリプト群を配置する。

各ファイルは単純な仕組みで、基本**一つの呼び出しクラスだけ**を記述する。
呼び出し側（claude）は、そのクラスをインスタンス化して `run()` を呼ぶだけでよい
（CLI 引数のパースはしない。`if __name__ == "__main__"` も置かない）。

    from DEM.claude_interface.world.list_places import ListPlaces
    ListPlaces(kind="村").run()

置き場所は `<領域>/<動詞_対象>.py`。領域はいまのところ次の四つ。

- `randomizer/` — ランダム生成（作る／確定する）
- `story/` — ストーリー生成モードの読み書き（材料を引く・本文を確定する）
- `sync/` — db と md の同期
- `world/` — 場所・種別・個体・語の一覧（読む専用）

各領域に共通する処理はクラスへ寄せ、その領域の入口の**上位**（`<領域>/_base.py`）
に置く。さらに四領域をまたいで共通する部分（db セッションを開いて渡す・
「確定する」系の実在確認とスキーマ列チェック等）は、一段上の
`DEM/claude_interface/_base.py` に置く。`_rows.py` と同じく、先頭が `_` の
ファイルはそれ自体が claude の呼ぶ入口ではない。

```
Entrypoint（claude_interface/_base.py）
├─ SessionEntrypoint            db セッションを開いて execute(session) へ渡す
│   ├─ CommitEntrypoint         「確定する」系の共通処理（parse/check_columns/check_exists）
│   │   ├─ randomizer.CommitDraft   → commit_character.py / commit_event.py
│   │   └─ story.StoryCommit        → commit_episode.py / set_episode_synced.py
│   ├─ world.WorldQuery          → list_kinds.py / list_objects.py / list_places.py / search_terms.py
│   └─ story.StoryQuery          → list_stories.py / read_*.py / start_story.py
└─ randomizer.RandomDraft        db に触れない下書き作成 → create_random_*.py
```

（`sync/export_db.py` は領域内に一件しかないので、`Entrypoint` を直接継ぐ）

読む側の中身は `DEM/data_access_logic/query/` にある（`common_query.py` が
モード 2 向け、`character_simulation_query.py` が人物の周辺を読む用、
`dictionary_query.py` が語（辞書）のキーワード検索用。
`story_createion_query.py` / `world_createion_query.py` はモード 1・3 向けの
置き場所として空けてあるだけで、まだ中身が無い）。
ここのファイルはその薄い呼び出し面で、**SQL は組み立てない**。
