#!/usr/bin/env python3
"""JSON で受け取った内容で、**既にある**筋書きを一件、db 上で直す、claude が呼ぶ入口。

新しく筋書きを作るのは `commit_plot.CommitPlot` の仕事。ここは、既に確定済みの
筋書きの欄(`text` の書き直しなど)を後から直すためだけの入口——`id` で対象を
指定し、渡した欄だけを上書きする(渡さなかった欄はそのまま)。

`id` の実在確認と、スキーマに無い欄の混入チェックは他の「確定する」入口と同じ。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Plot
from DEM.db.schema_pydantic import to_dict


class UpdatePlot(CommitDraft):
    """筋書きを一件、渡した欄だけ書き換えて db へ確定し、格納後の中身を返す。

    `plot` は JSON 文字列でも辞書でもよい。`id` は直す対象を指すので必須
    (`commit_plot.CommitPlot` と違い、ここでは無視しない)。
    """

    model = Plot

    def __init__(self, plot: str | dict):
        self.plot = plot

    def execute(self, session) -> dict:
        data = self.parse(self.plot)
        plot_id = data.pop("id", None)
        if plot_id is None:
            raise ValueError("id は必須(直す対象の筋書き)")
        self.check_columns(data)

        record = session.get(Plot, plot_id)
        if record is None:
            raise ValueError(f"id={plot_id} という筋書きが見つからない")

        for key, value in data.items():
            setattr(record, key, value)
        session.commit()
        return to_dict(record)
