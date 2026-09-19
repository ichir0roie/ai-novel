claudeが実行するスクリプト群を配置する。

各ファイルは単純な仕組みで、基本一つの呼び出し機能のみを記述する。

置き場所は `<領域>/<動詞_対象>.py`。領域はいまのところ次の四つ。

- `randomizer/` — ランダム生成（作る／確定する）
- `story/` — ストーリー生成モードの読み書き（材料を引く・本文を確定する）
- `sync/` — db と md の同期
- `world/` — 場所・種別・個体の一覧（読む専用）

読む側の中身は `DEM/data_access_logic/query/` にある（`common_query.py` が
モード 2 向け、`character_simulation_query.py` が人物の周辺を読む用。
`story_createion_query.py` / `world_createion_query.py` はモード 1・3 向けの
置き場所として空けてあるだけで、まだ中身が無い）。
ここのファイルはその薄い呼び出し面で、**SQL は組み立てない**。
