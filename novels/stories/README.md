# stories

ラノベの文章本体。作品ごとにディレクトリを作る。

```
novels/stories/<作品名>/
  meta.md           企画（core/templates/story-meta-template.md から）。**上段を持つ**
  plot.md           全体プロット（core/templates/plot-template.md から）
  episodes/
    001.md          第 1 話（core/templates/episode-template.md から）
    002.md
```

**作品は、必ずひとつの世界線の中で完結する。** どの世界線に立つかは `meta.md` に書く。
別の世界線の設定を混ぜない。混ぜたくなったら、それは別の作品である。

## 原則

- **1 話 1 ファイル。** ファイル名は 3 桁ゼロ埋め。
  **本文のファイルに上段（YAML）を書かない。** 原稿だけを置く。
  話数はファイル名、題は先頭の見出しから台帳へ入る（chronicle.md）
- **話の頭に作業メモを HTML コメントで置く。** 変化するもの・引きの型・前話からの接続
- **過去話は指示があるまで書き換えない。** 修正は差分がわかる形で
- **このディレクトリを書いているあいだ、世界の側を触らない。**
  生まれた設定はメモに控えて、「3 世界観更新モード」で戻す（workflow.md）
- **要約で済ませない。** 場面として書く。ダイジェストは読者が飛ばす
- **数を本文に出さない。** 記録の数は作者だけが見る（chronicle.md）

## 書く前と、書いたあと

```
python3 tools/novel.py episodes --story <作品名>          # 直前の 10 話を読む
（展開を考える）
python3 tools/novel.py brief --place <場所> --time <年>
（本文を書く）
python3 tools/novel.py check
```

**いちばん先に直前の 10 話を読む**（workflow.md 2-1）。
前の話を覚えていないまま展開を考えると、同じ場面を書き直すことになる。

断面に `--full` を付けない。**住人が知らないことを書いてしまう。**

## 進捗の見かた

```
python3 tools/novel.py episodes --story <作品名> --list   # 話数・題・字数
```

各作品の `meta.md` の「状態」欄と、`plot.md` の伏線管理表を見る。
世界の側の進み方は `python3 tools/novel.py brief` で見る。
