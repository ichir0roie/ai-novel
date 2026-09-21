#!/usr/bin/env python3
"""ランダムな個体(群)の下書きを一件、辞書として作る、claude が呼ぶ入口。

`DEM.randomizer.random_object_generator.build_object` の薄いラッパー。
**db には一切触れない。** 実在レコードを指す欄(`root_place_name`)の存在確認や、
実際の書き込みはしない——それは
`DEM.claude_interface.randomizer.commit_object.CommitObject` の仕事。

**`name` は仮の値のまま返る。** 国・組織・商会などの名は `IHG/naming.md`
(「対象ごとの当て方」の組織・機関。「〜機構」「〜管理局」にしない)に沿って
claude が決めてから、`text` や `root_place_name` と一緒に `CommitObject` に渡す。

**個体に `kind` の欄は無い。** 国か組織か商会かは `text` に書く。その個体が
何を決められるのか・誰に対して力を持つのかまで書いておくと、出来事の生成で
その個体が行為の主体として立つ(`IHG/chronicle.md`「出来事の text は記録として
書く」の `OBJECT_ACTION_INSTRUCTION`)。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import RandomDraft
from DEM.randomizer.random_object_generator import build_object


class CreateRandomObject(RandomDraft):
    """ランダムな個体(群)の下書きを一件、辞書として返す。"""

    builder = staticmethod(build_object)
