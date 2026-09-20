#!/usr/bin/env python3
"""JSON で受け取った筋書きを一件、db へ確定する、claude が呼ぶ入口。

`Plot` は、`DEM/local_ai/time_keeper/event_progression_generator.py` が
場所ごとに出来事を1件決めるときへ渡す「進めたい筋書き」。プロットを渡さない
まま自動生成を続けると間延びした展開ばかりになるため、作者・claude が
ここへ方向づけを置く。ランダム生成の対になる下書き作成器は持たず
(筋書きは作者の意図そのものなので乱数で作らない)、辞書をそのまま
受け取って確定するだけにとどめる。

実在レコードを指す欄(`location_id`)は、渡された id が db に実在するかを
ここで確かめてから書き込む。`location_id` を省く(または `None`)と、
場所を問わず全ての出来事生成に渡る筋書きになる。`text`(`MarkdownBase` 由来。
進めたい筋書きの本文)は必須。`start`〜`end` を渡すと、その筋書きが生成へ
渡るのをその期間だけに絞れる(省けば期間を問わず渡り続ける)。スキーマに
無い欄が混じっていたら(`DEM/db/schema.py` の `Plot` の列と照らして)
そこで止める。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Location, Plot
from DEM.db.schema_pydantic import to_dict


class CommitPlot(CommitDraft):
    """筋書きを一件、db へ確定して、格納後の中身を辞書で返す。

    `plot` は JSON 文字列でも辞書でもよい。`id` キーは無視する
    (採番は db に任せる)。
    """

    model = Plot

    def __init__(self, plot: str | dict):
        self.plot = plot

    def execute(self, session) -> dict:
        data = self.parse(self.plot)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("text"):
            raise ValueError("text は必須")

        self.check_exists(session, Location, data.get("location_id"), "location_id")

        record = Plot(**data)
        session.add(record)
        session.commit()
        return to_dict(record)
