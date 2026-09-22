# ai-novel

AI にラノベを書いてもらうためのプロジェクト。

**仕組み(`DEM/`)と記録・本文(`novel.db`)を別の場所に置き、「毎回ゼロから考え直さない」ことを目的にしている。**

すべての作品は現実の過去、現在、未来で起こっている。平行世界を許容する。

## ディレクトリ

| ディレクトリ | 役割                                                             |
| ------------ | ---------------------------------------------------------------- |
| `DEM/`       | 仕組み。db の形・入口・問い合わせ・ローカル AI                   |
| `novel.db`   | **世界の記録と本文そのもの**(SQLite)                             |
| `worlds/`    | db から書き出した**読む専用の写し**(`ExportDb`。無くてもよい)    |
| `oracle/`    | 覚書とアイデア置き場                                             |
| `CLAUDE.md`  | **Claude 向けの作業指針**                                         |

```
DEM/
  db/                 **記録の形(SQLAlchemy)。列はここ一か所で決まる**
                      alembic/ にマイグレーション
  data_access_logic/  引き方(Select の組み立て)。SQL 文字列は組まない
  randomizer/         db に触れない下書き作り(factory)と乱数
  ai/                 AI に生成させる側をまとめた置き場
    instructions/     常駐ループのプロンプトに埋め込む基準の定数(Python)
    time_keeper/      常駐ループの本体。世界を進める生成器(人物・出来事・場所・寿命)。AI は引数で受け取る
    local_ai/         ローカル AI(Ollama)の client と、それでループを回す入口
    claude_code/      Claude Code(`claude -p`)の client と、それでループを回す入口。本文(episode)もここが書く
      interface/      **Claude が呼ぶ入口。db に触れるのはここ越しだけ**
                      randomizer/ story/ world/ sync/
  tool/               md への書き出し・読み戻し、危険操作(danger/seed_mock_db で全テーブルにモックデータを流し込める)
```

## Claude はもう物語を直接生成しない

出来事・人物(国・組織などの対象も含む)・場所も、本文(`episode`)も、`DEM/ai/local_ai/`(常駐ループ)
が生成する。Claude がこのリポジトリで担うのは、その生成の仕組み
(`DEM/ai/local_ai/` `DEM/ai/claude_code/interface/` など)を作る・直す開発作業。

## 触り方

```
pip install -r requirements.txt
```

**db を直に開かない。** 読むのも書くのも `DEM/ai/claude_code/interface/` の入口を
import して呼ぶ。入口は一ファイル一クラスで、CLI 引数のパースをしない。

```python
from DEM.ai.claude_code.interface.world.list_places import ListPlaces
ListPlaces(kind="村").run()
```

今ある入口の一覧は **`DEM/ai/claude_code/interface/readme.md` の表**にある。そこに無い操作は「まだ無い」。
必要になったら同じ readme の「作り方」に沿って足す。

## 命名規約

- レコードの名(場所・人物・語・作品)は**日本語でよい。**
  参照は名前ではなく **id** で持つ
- 時刻は `y/mm/dd hh:mm:ss`。後ろから欠けた分は書かなくてよい(`4360/7/12` / `4360`)。
  **年に上限はない**(`DEM/db/stamp.py`)
- 話数は数字だけ(1, 2, 3)。**ゼロ埋めしない**
- スクリプト名は半角英数とアンダースコア(例: `DEM/randomizer/roll.py`)

## AI に依頼するときのコツ

Claude への依頼は、いまは物語の生成そのものではなく `DEM/ai/local_ai/` の
開発・保守が対象になる。「イベントを起こして」「キャラを足して」ではなく、
「出来事が生まれる確率を上げて」「この場所にキャラが生まれない不具合を
直して」のように、**生成の仕組みへの変更**として頼む。
