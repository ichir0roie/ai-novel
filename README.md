# ai-novel

※プロット含め、致命的なネタバレが含まれている。


AI にラノベを書いてもらうためのプロジェクト。

**仕組み(`DEM/`)と記録・本文(`novel.db`)を別の場所に置き、「毎回ゼロから考え直さない」ことを目的にしている。**

すべての作品は現実の過去、現在、未来で起こっている。平行世界を許容する。

## 特徴

- **世界が先、本文が後。** 場所・人物・人物相関・出来事・語をすべて `novel.db` に記録し、
  本文(`episode`)はその時点・その場所の断面を引いてから書く
- **AI が自動で世界を進める。** 常駐ループ(`DEM/ai/time_keeper/`)が時間を進め、
  人物の誕生・寿命、出来事、場所を生成して db に積む
- **AI を差し替えられる。** 同じループをローカル AI(Ollama)でも Claude Code(`claude -p`)でも回せる
- **db に触れる入口を一本化。** Claude は `DEM/ai/claude_code/interface/` の入口越しにだけ読み書きする。
  下書きを「作る」側は db に触れず辞書を返し、「確定する」側が実在確認と列チェックをして書き込む
- **md で読める・直せる。** `ExportDb` / `ImportDb` で db と `worlds/` の md を往復し、
  星ごとの地図(svg / html)と人物相関図も書き出す
- **本文は種から書く。** 話ごとに作者が `key`(場面割りと狙い)を置き、AI か作者が `text` を書く
- **時間に上限がない。** 年は何桁でもよく(ノウル一万年代など)、遠未来の世界線も同じ仕組みで扱う
- **テストは本番に触れない。** `novel.test.db` とモック AI で、AI 無しにループを再走できる



## ディレクトリ

| ディレクトリ | 役割                                                          |
| ------------ | ------------------------------------------------------------- |
| `DEM/`       | 仕組み。db の形・入口・問い合わせ・ローカル AI                |
| `novel.db`   | **世界の記録と本文そのもの**(SQLite)                          |
| `worlds/`    | db から書き出した**読む専用の写し**(`ExportDb`。無くてもよい) |
| `oracle/`    | 覚書とアイデア置き場                                          |
| `CLAUDE.md`  | **Claude 向けの作業指針**                                     |

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
  tool/               md への書き出し・読み戻し、危険操作(danger/)、テスト用の道具(test/。必ず novel.test.db を使う。
                      mock_ai_client で AI 無しに redrive_mock_world を回す、seed_mock_db で全テーブルにモックデータを流し込む)
```

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


# 成果物一覧


<https://syosetu.com/usernovelmanage/top/ncode/3323080/>