# 進め方

**いまは、出来事・人物・個体・場所も、本文(`episode`)も、Claude が対話の
中で直接生成することをしない。** 生成は `DEM/local_ai/`(常駐ループ)に
一本化した。Claude がこのリポジトリで担うのは、その生成の仕組み
(`DEM/local_ai/` `DEM/claude_interface/` `DEM/data_access_logic/`
`DEM/db/`)を作る・直す**開発作業**であって、執筆作業そのものではない。

## Claude はもう何を生成しないか

- **本文(`episode`)。** 話を書く入口はまだ無い。書けるようにする番が来ても、
  それは Claude が対話の中で直接書くのではなく、`DEM/local_ai/` 側の
  生成として作る
- **出来事(`event`)。** `DEM/local_ai/time_keeper/event_progression_generator.py`
  `character_lifespan.py` が生成から確定まで行う
- **人物(`character`)・個体(`object`)・場所(`location`)。**
  同じく `time_keeper/random_*_generator.py` が生成する
- **筋書き(`plot`)を含む、それ以外の世界のレコードすべて**

対話の中で「イベントを起こして」「キャラを足して」と頼まれても、
Claude 自身が `CommitEvent` `CommitCharacter` のような確定する入口を
呼んで db に書き込むことはしない。**足りない・止まっているなら、
常駐ループ側(生成の確率・条件・`Plot`)を直す。**

常駐ループの起動・停止だけは、運用タスクとして直接呼んでよい
(生成そのものはローカル AI が行い、Claude はループの開始・打ち切りを
指示するだけなので、これは「Claude が直接生成する」ことにはあたらない)。

```python
DEM.local_ai.time_keeper.main.claude_main()
```

## Claude が実際にすること

`DEM/local_ai/` の生成器・`DEM/claude_interface/` の入口・
`DEM/data_access_logic/` の引き方・`DEM/db/schema.py` のレコードの形——
このどれかを足す・直すのが仕事になる。

- **生成の基準(出来事の書き方・名づけ・なろう系回避)を変えたいときは
  `IHG/ai_instructions/*.py` を直す。** どちらが正本かはファイルごとに
  決まっている(`IHG/README.md`「常駐ループへ渡す基準」)。なぜその基準に
  したかの経緯は `IHG/chronicle.md`(出来事)`IHG/naming.md`(名づけ)
  `IHG/principles.md`(なろう系回避)に残っている。**文面を変えたら、
  正本の側とその参照元を両方直す**
- レコードの欄を増やす・変えるときは `DEM/db/schema.py` を直し、
  alembic でマイグレーションを一本切る(`DEM/db/alembic/`)
- db を読み書きする新しい入口が要るときは
  `DEM/claude_interface/readme.md`「作り方」に沿って足す。
  **今ある入口の一覧も同じ readme にある**

## それでも守ること: db は DEM/claude_interface 越しにしか触らない

**`novel.db` を直に開かない。** `DEM.db.schema` を直接 import して
読み書きしない、`sqlite3` で `novel.db` を直接開かない。動作確認や
調査で db の中身を見るときも、読む側の入口
(`DEM/claude_interface/world/list_*.py` `search_terms.py` など)を
import して呼ぶ。

**SQL は組み立てない。** 引く条件は時刻とレコードの id で表し、
足りない引き方は `DEM/data_access_logic/query/` に関数を足して、
`DEM/claude_interface/` に一つ入口を被せる。

**`worlds/` の md も直に開かない**(md は db の写し。書き出しは
`DEM.claude_interface.sync.export_db.ExportDb().run()`)。**md を直しても
db には戻らない**(戻す向きの `import_db` もあるが、db を本体として
扱う前提は変わらない)。

---

## 過去の三モード構成について

以前はここに「世界観構成・ストーリー生成・世界観更新」という三つの
モードと、その中で Claude が `CreateRandom*`/`Commit*`/`ReadBrief`/
`CommitEpisode` などを対話の中で直接呼ぶ手順を書いていた。**その手順は
もう無い。** 実行に使っていた `IHG/entrypoints.md` `IHG/structure.md`
`IHG/characters.md` `IHG/dialogue.md` `IHG/checklist.md`
`IHG/writing-style.md` と、`DEM/claude_interface/world/advance_time.py`
は削除した。当時の判断を確認したいときは、これより前のコミットログを見る。
