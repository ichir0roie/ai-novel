# stories / 地球系

この宇宙のラノベの文章本体。作品ごとにディレクトリを作る。

**作品は、必ずひとつの宇宙の中で完結する。** だから `stories/` は `worlds/<宇宙名>/` の下にある。
別の宇宙の設定を混ぜない。混ぜたくなったら、それは別の宇宙で書くべき話である。

```
worlds/地球系/stories/<作品名>/
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
- **設定を変えたくなったら先に `../` 側（world.md・各星のファイル）を直す。**
  本文だけ直すと矛盾が残る
- **書く前に断面を取り、書いたら台帳へ戻す。** `core/chronicle.md`

## 書く前と、書いたあと

```
python3 tools/chronicle.py brief --world 地球系 --star 入植星 --year 4360 --place mushvan-land
（本文を書く）
python3 tools/chronicle.py add --world 地球系 --table event --set 年=... --set 出来事=...
python3 tools/chronicle.py check --world 地球系
```

断面に `--full` を付けない。**住人が知らないことを書いてしまう。**

## 進捗の見かた

各作品の `meta.md` の「状態」欄と、`plot.md` の伏線管理表を見る。
世界の側の進み方は `python3 tools/chronicle.py brief` で見る。
