# ai-novel

AI にラノベを書いてもらうためのプロジェクト。

設定・技術・本文をそれぞれ別の場所に置き、「毎回ゼロから考え直さない」ことを目的にしている。

## ディレクトリ

| ディレクトリ | 役割 |
| --- | --- |
| `core/` | 共通の作業方針やテクニック。どの世界観・どの作品にも効く知見を書き留める |
| `worlds/` | 世界観ごとの設定やオブジェクト（地名・組織・魔法体系・キャラクターなど） |
| `stories/` | それぞれのラノベの文章本体。プロットと各話の原稿 |
| `tools/` | Python ツール群。執筆を補助するスクリプトはここに置く |

```
core/
  principles.md       プロジェクトの目的と禁止事項（最優先）
  naming.md           用語と名づけの基準（日本語として自然に）
  writing-style.md    文体の基本方針
  structure.md        構成・プロットのテクニック
  characters.md       キャラ造形のテクニック
  dialogue.md         会話文のテクニック
  workflow.md         執筆の進め方（設定 → プロット → 本文 → 推敲）
  checklist.md        書き上げたあとの推敲チェックリスト
  templates/          世界観・キャラ・プロット・各話のひな形

tools/
  roll.py             乱数ツール（設定をアバウトに決めるとき）
  tables.json         乱数テーブル

worlds/<宇宙名>/        1 ディレクトリ = 1 宇宙
  world.md            宇宙全体の設定（暦・共通現象・星どうしの関係）
  rolls.md            乱数ログ（シードと調整理由）
  glossary.md         固有名詞・用語集
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

1. `core/principles.md` と `core/workflow.md` を読む
2. 世界観を `core/templates/world-template.md` から起こして `worlds/<名前>/` に置く
3. 作品を `core/templates/story-meta-template.md` と `plot-template.md` から起こして `stories/<名前>/` に置く
4. `stories/<名前>/episodes/` に本文を書く

## 命名規約

- 宇宙・星のディレクトリ名は日本語でよい（`worlds/<宇宙名>/<星名>/`）。
  中身がひと目で分かる名前を優先する
- スクリプトなど日本語が扱いにくいものは半角英数とハイフン（例: `tools/roll.py`）
- 各話ファイルは 3 桁ゼロ埋め（`001.md`, `002.md`）

## AI に依頼するときのコツ

- 「どの世界観か」「どの作品か」をパスで指定する（例: `worlds/<宇宙名>` を使って `stories/<作品名>` の 3 話を書いて）
- 新しく決めた設定は本文だけに置かず、必ず `worlds/` 側にも書き戻す
- 文体の好みが変わったら `core/writing-style.md` を直す。次からの全作品に効く
