#!/usr/bin/env python3
"""座標は [経度, 緯度] の順(GeoJSON と同じ)。"""
from __future__ import annotations

import json

__all__ = ["parse_polygon", "outer_ring", "polygon_center"]


def _position(value) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"座標は [経度, 緯度] の二つ組: {value!r}")
    try:
        lon, lat = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        raise ValueError(f"座標は数: {value!r}") from None
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError(f"経度は -180〜180、緯度は -90〜90: {value!r}")
    return [lon, lat]


def _ring(value) -> list[list[float]]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"環は座標の並び: {value!r}")
    ring = [_position(p) for p in value]
    if ring and ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    if len(ring) < 4:
        raise ValueError(f"環には三つ以上の異なる座標が要る: {value!r}")
    return ring


def _is_position(value) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) for v in value))


def parse_polygon(value) -> dict | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ValueError(f"polygon は GeoJSON の Polygon か座標の並び: {value!r}") from None
    if isinstance(value, dict):
        if value.get("type") != "Polygon":
            raise ValueError(f'polygon の type は "Polygon": {value.get("type")!r}')
        rings = value.get("coordinates")
    elif isinstance(value, (list, tuple)):
        rings = [value] if value and _is_position(value[0]) else value
    else:
        raise ValueError(f"polygon は GeoJSON の Polygon か座標の並び: {value!r}")
    if not isinstance(rings, (list, tuple)) or not rings:
        raise ValueError("polygon の coordinates が空")
    return {"type": "Polygon", "coordinates": [_ring(r) for r in rings]}


def outer_ring(polygon: dict) -> list[list[float]]:
    ring = polygon["coordinates"][0]
    return ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else list(ring)


def polygon_center(polygon: dict) -> tuple[float, float]:
    ring = outer_ring(polygon)
    return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
