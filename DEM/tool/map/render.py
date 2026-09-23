#!/usr/bin/env python3
"""地図を書き出す。`export_db` から呼ばれる。

- 星ごとの SVG: その星の md と同じディレクトリに `{id}_map.svg`
- 全ての星をまとめた HTML: `worlds/maps/map.html`
"""
from __future__ import annotations

import os

from DEM.tool.map.collect import collect_planets
from DEM.tool.map.render_html import render_html
from DEM.tool.map.render_svg import render_svg

__all__ = ["render_maps"]


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def render_maps(session, root: str) -> list[str]:
    """書き出したファイルのパスを返す。"""
    table_dir = os.path.join(root, "location")
    planets = collect_planets(session)
    written = []
    for entry in planets:
        planet = entry["planet"]
        dir_path = os.path.join(table_dir, planet["directory_path"]) if planet["directory_path"] else table_dir
        path = os.path.join(dir_path, f"{planet['id']}_map.svg")
        _write(path, render_svg(planet, entry["points"], entry["shapes"]))
        written.append(path)
    html_path = os.path.join(root, "maps", "map.html")
    _write(html_path, render_html(planets))
    written.append(html_path)
    return written
