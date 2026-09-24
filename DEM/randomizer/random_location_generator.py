#!/usr/bin/env python3
"""ランダムな場所(Location)一件分の下書きを辞書として組む。db には触れない。"""
from __future__ import annotations

import factory


class LocationFactory(factory.DictFactory):
    name = factory.Sequence(lambda n: f"仮の土地{n}")
    kind = "大陸"
    text = ""

    parent_id = None
    location_world = None
    location_planet = None
    location_longitude = None
    location_latitude = None
    location_altitude = None
    area = None
    environment = None
    sample_region = None
    sample_culture = None
    sample_era = None
    start = None
    end = None
    active_random_generation = False


def build_location(**overrides) -> dict:
    return LocationFactory.build(**overrides)
