#!/usr/bin/env python3
"""ある場所から見た、同じ星の上の他の場所の方角・距離・高低差を近い順に出す、claude が呼ぶ入口。

    ListNeighbors(place_id=60).run()
    ListNeighbors(place_id=60, kind="国", limit=5).run()
"""
from __future__ import annotations

from ai.claude_code.interface._base import SessionEntrypoint
from data_access_logic.query import common_query
from db.schema import Location
from tool.map.collect import planet_dict, point_dict
from tool.map.geometry import (
    altitude_diff_text, angular_distance_deg, bearing_deg, bearing_name, distance_km, distance_text,
)


class ListNeighbors(SessionEntrypoint):
    """`{"place": {...}, "planet": {...}, "neighbors": [近い順]}` を返す。各 neighbor に文の `summary` を付ける。"""

    def __init__(self, place_id: int, kind: str | None = None, limit: int | None = None):
        self.place_id = int(place_id)
        self.kind = kind
        self.limit = limit

    def execute(self, session) -> dict:
        origin = session.get(Location, self.place_id)
        if origin is None:
            raise common_query.NotFoundError(f"id={self.place_id} の場所が無い")
        if origin.location_longitude is None or origin.location_latitude is None:
            raise ValueError(f"{origin.name}(id={origin.id})は経緯度を持たない(面の場所か、座標が未記入)")
        planet = session.get(Location, origin.location_planet) if origin.location_planet is not None else None
        if planet is None:
            raise ValueError(f"{origin.name}(id={origin.id})は星(location_planet)が決まっていない")

        radius = planet_dict(planet)["radius_km"]
        rows = []
        for place in session.scalars(common_query.places_on_planet_select(planet.id)).all():
            if place.id == origin.id or (self.kind is not None and place.kind != self.kind):
                continue
            rows.append(self._row(session, origin, place, radius))
        rows.sort(key=lambda r: (r["distance_deg"], r["id"]))
        if self.limit is not None:
            rows = rows[: int(self.limit)]
        return {"place": point_dict(session, origin), "planet": planet_dict(planet), "neighbors": rows}

    @staticmethod
    def _row(session, origin, place, radius) -> dict:
        lon1, lat1 = origin.location_longitude, origin.location_latitude
        lon2, lat2 = place.location_longitude, place.location_latitude
        deg = angular_distance_deg(lon1, lat1, lon2, lat2)
        km = distance_km(radius, lon1, lat1, lon2, lat2)
        bearing = bearing_deg(lon1, lat1, lon2, lat2)
        diff = (float(place.location_altitude) - float(origin.location_altitude)
                if place.location_altitude is not None and origin.location_altitude is not None else None)
        row = point_dict(session, place)
        row.update({
            "distance_deg": round(deg, 2),
            "distance_km": None if km is None else round(km),
            "bearing_deg": round(bearing),
            "bearing": "同じ経緯度" if deg < 0.01 else bearing_name(bearing),
            "altitude_diff_m": diff,
        })
        parent = f"・{row['parent_name']}" if row["parent_name"] else ""
        where = "同じ経緯度" if deg < 0.01 else f"{row['bearing']} {distance_text(km, deg)}"
        row["summary"] = f"{row['name']}({row['kind'] or '種別なし'}{parent}): {where}、{altitude_diff_text(diff)}"
        return row
