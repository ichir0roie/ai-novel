# ai-novel

AI にラノベを書いてもらうためのプロジェクト。

**方針・技術(`IHG/`)、仕組み(`DEM/`)、記録と本文(`novel.db`)をそれぞれ別の
場所に置き、「毎回ゼロから考え直さない」ことを目的にしている。**

すべての作品は現実の過去、現在、未来で起こっている。平行世界を許容する。

## ディレクトリ

| ディレクトリ | 役割                                                             |
| ------------ | ---------------------------------------------------------------- |
| `IHG/`       | 共通の作業方針とテクニック。どの世界線・どの作品にも効く知見     |
| `DEM/`       | 仕組み。db の形・入口・問い合わせ・ローカル AI                   |
| `novel.db`   | **世界の記録と本文そのもの**(SQLite)                             |
| `worlds/`    | db から書き出した**読む専用の写し**(`ExportDb`。無くてもよい)    |
| `oracle/`    | 覚書とアイデア置き場                                             |
| `CLAUDE.md`  | **Claude 向けの作業指針**                                         |

```
IHG/
  principles.md       プロジェクトの目的と禁止事項(最優先)
  workflow.md         **進め方。Claude はもう本文・出来事・人物などを直接生成しない**
  chronicle.md        **記録の取り方と、話を尽きさせない仕組み**
  naming.md           用語と名づけの基準(日本語として自然に)
  ai_instructions/    常駐ループのプロンプトに埋め込む基準の定数(Python)。
                      いま生成に実際に使われているのはここだけ

DEM/
  db/                 **記録の形(SQLAlchemy)。列はここ一か所で決まる**
                      alembic/ にマイグレーション
  claude_interface/   **Claude が呼ぶ入口。db に触れるのはここ越しだけ**
                      randomizer/ story/ world/ sync/
  data_access_logic/  引き方(Select の組み立て)。SQL 文字列は組まない
  randomizer/         db に触れない下書き作り(factory)と乱数
  local_ai/           ローカル AI。常駐ループ(time_keeper/)が世界を進める
  tool/               md への書き出し・読み戻し、危険操作
```

## Claude はもう物語を直接生成しない

出来事・人物(国・組織などの対象も含む)・場所も、本文(`episode`)も、`DEM/local_ai/`(常駐ループ)
が生成する。Claude がこのリポジトリで担うのは、その生成の仕組み
(`DEM/local_ai/` `DEM/claude_interface/` など)を作る・直す開発作業。
詳しくは `IHG/workflow.md`。

## 触り方

```
pip install -r requirements.txt
```

**db を直に開かない。** 読むのも書くのも `DEM/claude_interface/` の入口を
import して呼ぶ。入口は一ファイル一クラスで、CLI 引数のパースをしない。

```python
from DEM.claude_interface.world.list_places import ListPlaces
ListPlaces(kind="村").run()
```

今ある入口の一覧は **`DEM/claude_interface/readme.md` の表**にある。そこに無い操作は「まだ無い」。
必要になったら同じ readme の「作り方」に沿って足す。

## 命名規約

- レコードの名(場所・人物・語・作品)は**日本語でよい。**
  参照は名前ではなく **id** で持つ
- 時刻は `y/mm/dd hh:mm:ss`。後ろから欠けた分は書かなくてよい(`4360/7/12` / `4360`)。
  **年に上限はない**(`DEM/db/stamp.py`)
- 話数は数字だけ(1, 2, 3)。**ゼロ埋めしない**
- スクリプト名は半角英数とアンダースコア(例: `DEM/randomizer/roll.py`)

## AI に依頼するときのコツ

Claude への依頼は、いまは物語の生成そのものではなく `DEM/local_ai/` の
開発・保守が対象になる。「イベントを起こして」「キャラを足して」ではなく、
「出来事が生まれる確率を上げて」「この場所にキャラが生まれない不具合を
直して」のように、**生成の仕組みへの変更**として頼む。
