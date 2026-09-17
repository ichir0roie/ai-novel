# stories

ラノベの文章本体。作品ごとにディレクトリを作る。

```
stories/<story-id>/
  meta.md           企画（core/templates/story-meta-template.md から）
  plot.md           全体プロット（core/templates/plot-template.md から）
  episodes/
    001.md          第 1 話（core/templates/episode-template.md から）
    002.md
```

## 原則

- **1 話 1 ファイル。** ファイル名は 3 桁ゼロ埋め
- **話の頭に作業メモを HTML コメントで置く。** 変化するもの・引きの型・前話からの接続
- **過去話は指示があるまで書き換えない。** 修正は差分がわかる形で
- **設定を変えたくなったら先に `worlds/` を直す。** 本文だけ直すと矛盾が残る

## 進捗の見かた

各作品の `meta.md` の「状態」欄と、`plot.md` の伏線管理表を見る。
