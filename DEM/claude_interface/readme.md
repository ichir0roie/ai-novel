claudeが実行するスクリプト群を配置する。

各ファイルは単純な仕組みで、基本**一つの呼び出しクラスだけ**を記述する。
呼び出し側(claude)は、そのクラスをインスタンス化して `run()` を呼ぶだけでよい
(CLI 引数のパースはしない。`if __name__ == "__main__"` も置かない)。

    from DEM.claude_interface.world.list_places import ListPlaces
    ListPlaces(kind="村").run()

**db に触れるのはここ越しだけ。** `DEM/db/` `DEM/randomizer/`
`DEM/data_access_logic/` は下地の実装であって、claude が直接呼ぶ入口ではない。
**この下に無い操作は「まだ無い」。** 推測で呼び出そうとせず、必要になったら
下の作り方に沿って足すか、作者に相談する(CLAUDE.md)。

(例外: `DEM/local_ai/time_keeper/` の常駐ループの起動だけは、運用タスクとして
`DEM.local_ai.time_keeper.main.claude_main()` を直接呼んでよい。詳しくは
`IHG/workflow.md`)

**世界の生成(出来事・人物・場所・本文)はもう `DEM/local_ai/` の
常駐ループだけが行う。** `randomizer/` `story/` の「作る」「確定する」入口も
残っているが、Claude が対話の中でこれらを呼んで内容を直接決めることは
しない(`IHG/workflow.md`「Claude はもう何を生成しないか」)。

置き場所は `<領域>/<動詞_対象>.py`。領域はいまのところ次の四つ。

- `randomizer/` — ランダム生成(作る／確定する)と、確定済みレコードの修正
- `story/` — 話(`story`/`episode`)まわりの読み書き(材料を引く・本文を確定する)
- `sync/` — db と md の同期
- `world/` — 場所・人物・語・出来事・筋書きの一覧(読む専用)

## 今ある入口

| 領域         | 入口                                                                                                                             |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| `randomizer/` | `create_random_character` `create_random_place` `create_random_event`(db に触れない下書き)                |
|              | `commit_character` `commit_place` `commit_event` `commit_plot` `commit_character_plot`(確定する) |
|              | `update_character` `update_place` `update_plot` `update_character_plot` `delete_place`(確定済みを直す・消す)       |
| `story/`     | `list_stories` `list_unsynced_episodes` `start_story` `read_episodes` `read_cast` `read_brief` `read_character` `read_surroundings` `read_events` |
|              | `commit_episode` `set_episode_synced`                                                                                             |
| `world/`     | `list_places` `list_characters` `list_events` `list_plots` `list_character_plots` `search_terms`                    |
| `sync/`      | `export_db`(db → md の写し) `import_db`(md → db。逆向き)                                                                          |

**`term`(語)を確定する入口はまだ無い。** 検索(`search_terms`)だけがある。

## 作り方

- **「作る」と「確定する」を別ファイルに分ける。** 「作る」側(`create_random_*`)は
  db に一切触れず、素の辞書 / JSON を返すだけ。db を触るのは「確定する」側だけ
- 辞書 / JSON で受け渡しするのは、Bash 呼び出しをまたいでも(＝プロセスが
  切り替わっても)中身を運べるようにするため。SQLAlchemy のオブジェクトや
  session を返すと、次の呼び出しでは中身が失われる
- 実在レコードを指す欄(id)は、確定する側が呼び出し時に db に居るか確かめる
  (`check_exists`)。スキーマに無い欄が混ざっていたらそこで止める(`check_columns`)

各領域に共通する処理はクラスへ寄せ、その領域の入口の**上位**(`<領域>/_base.py`)
に置く。さらに四領域をまたいで共通する部分(db セッションを開いて渡す・
「確定する」系の実在確認とスキーマ列チェック等)は、一段上の
`DEM/claude_interface/_base.py` に置く。`_rows.py` と同じく、先頭が `_` の
ファイルはそれ自体が claude の呼ぶ入口ではない。

```
Entrypoint(claude_interface/_base.py)
├─ SessionEntrypoint            db セッションを開いて execute(session) へ渡す
│   ├─ CommitEntrypoint         「確定する」系の共通処理(parse/check_columns/check_exists)
│   │   ├─ randomizer.CommitDraft   → commit_*.py / update_*.py / delete_place.py
│   │   └─ story.StoryCommit        → commit_episode.py / set_episode_synced.py
│   ├─ world.WorldQuery          → list_*.py / search_terms.py
│   └─ story.StoryQuery          → list_*.py / read_*.py / start_story.py
└─ randomizer.RandomDraft        db に触れない下書き作成 → create_random_*.py
```

(`sync/` の二つは db セッションを開かないので、`Entrypoint` を直接継ぐ)

## 引き方は query 側にある

読む側の中身は `DEM/data_access_logic/query/` にある。

| モジュール                     | 何のため                                                     |
| ------------------------------ | ------------------------------------------------------------ |
| `common_query.py`              | 時刻の扱い・断面・顔ぶれ・場所の道筋                         |
| `character_simulation_query.py` | 人物を軸に周辺を読む(`read_surroundings`)                   |
| `dictionary_query.py`          | 語(辞書)のキーワード検索                                     |
| `story_createion_query.py`     | 場所に掛かる筋書き(`plot`)・人物に掛かる筋書き(`character_plot`)の読み出し |
| `world_createion_query.py`     | 生きている人物、広さの整合、進行中の判定               |

ここのファイルはその薄い呼び出し面で、**SQL は組み立てない。**
引く条件は時刻とレコードの id だけで表す。足りない引き方が出てきたら
query 側に関数を足して、ここに入口を一つ被せる。
