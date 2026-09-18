# ai-novel

AI にラノベを書いてもらうためのプロジェクト。

設定・技術・本文をそれぞれ別の場所に置き、「毎回ゼロから考え直さない」ことを目的にしている。

## ディレクトリ

| ディレクトリ | 役割                                                                     |
| ------------ | ------------------------------------------------------------------------ |
| `core/`      | 共通の作業方針やテクニック。どの世界観・どの作品にも効く知見を書き留める |
| `worlds/`    | 世界観ごとの設定・台帳・**本文**。1 ディレクトリ = 1 宇宙                |
| `tools/`     | Python ツール群。執筆を補助するスクリプトはここに置く                    |

すべての作品は現実の過去、現在、未来で起こっている。
平行世界を許容する。

```
core/
  principles.md       プロジェクトの目的と禁止事項（最優先）
  naming.md           用語と名づけの基準（日本語として自然に）
  writing-style.md    文体の基本方針
  structure.md        構成・プロットのテクニック
  characters.md       キャラ造形のテクニック
  dialogue.md         会話文のテクニック
  workflow.md         執筆の進め方（設定 → プロット → 本文 → 推敲）
  chronicle.md        世界の記録の取り方と、話を尽きさせない仕組み
  checklist.md        書き上げたあとの推敲チェックリスト
  templates/          世界観・キャラ・プロット・各話のひな形

tools/
  roll.py             乱数ツール（設定をアバウトに決めるとき）
  tables.json         乱数テーブル
  schema.py           台帳の形（SQLAlchemy）。DB と表の列はここ一か所で決まる
  ledger.py           マークダウンの読み書きと、DB への取り込み
  chronicle.py        台帳ツールの入口（build / check / brief / add …）

worlds/<宇宙名>/        1 ディレクトリ = 1 宇宙。**作品もこの中で完結する**
  world.md            宇宙全体の設定（暦・共通現象・星どうしの関係）
  rolls.md            乱数ログ（シードと調整理由）
  glossary.md         固有名詞・用語集
  glossary.md         用語の索引。自動生成（chronicle.py index）
  records/            台帳（表）。時間つきの記録（→ core/chronicle.md）
    config.json       星・光の遅れ・物語の現在
    場所.md 出来事.md 行動.md 指標.md 関係.md 火種.md
  terms/<語>.md        用語。**1 レコード 1 ファイル**（front matter ＋ 文章）
  concepts/<名>.md     概念。同上
  stories/<作品名>/     本文
    meta.md           企画
    plot.md           全体プロット
    episodes/001.md   1 ファイル 1 話
  <星名>/             天文・歴史・社会
    characters/       人物・組織・国。**1 レコード 1 ファイル**
    objects/          道具・現象・施設。同上
  world.db            台帳を組み上げた SQLite。git には入れない
  <星名>/
    planet.md         天文・地理・空気感
    history.md        年表と争点
    society.md        種族・国家・制度
    characters/*.md   登場人物
    objects/*.md      アイテム・組織・地名などの個別設定

stories/<作品名>/
  meta.md             企画（ログライン・ターゲット・使う世界観）
  plot.md             全体プロット
  episodes/001.md     本文（1ファイル 1話）
```

## 書きはじめかた

```
pip install -r requirements.txt
```

1. `core/principles.md` と `core/workflow.md` を読む
2. 宇宙を起こす（`python3 tools/chronicle.py init --world <宇宙名>`）。
   設定は `core/templates/world-template.md` から `worlds/<宇宙名>/` に置く
3. 作品を `core/templates/story-meta-template.md` と `plot-template.md` から起こして
   `worlds/<宇宙名>/stories/<作品名>/` に置く
4. **書く前に断面を取る**（`python3 tools/chronicle.py brief --star <星> --year <年>`）
5. `worlds/<宇宙名>/stories/<作品名>/episodes/` に本文を書く
6. **書けたら台帳に戻す**（`chronicle.py add` → `chronicle.py check`）

## 命名規約

- 宇宙・星のディレクトリ名は日本語でよい（`worlds/<宇宙名>/<星名>/`）。
  中身がひと目で分かる名前を優先する
- スクリプトなど日本語が扱いにくいものは半角英数とハイフン（例: `tools/roll.py`）
- 各話ファイルは 3 桁ゼロ埋め（`001.md`, `002.md`）

## AI に依頼するときのコツ

- 「どの宇宙か」「どの作品か」をパスで指定する（例: `worlds/<宇宙名>/stories/<作品名>` の 3 話を書いて）
- 新しく決めた設定は本文だけに置かず、必ず `worlds/` 側にも書き戻す
- キャラ・物・用語・概念は **1 つにつき 1 ファイル**。`chronicle.py template --kind 人物` で雛形が出る
- 続きを書かせるときは話数ではなく**年と場所**で指定する（例: `--star 入植星 --year 4362 の断面から 2 話`）
- 文体の好みが変わったら `core/writing-style.md` を直す。次からの全作品に効く
