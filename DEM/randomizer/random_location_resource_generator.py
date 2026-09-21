#!/usr/bin/env python3
"""ランダムな場所の資源(LocationResource)一件分の下書きを辞書として組む。db には触れない。"""
from __future__ import annotations

import factory


class LocationResourceFactory(factory.DictFactory):
    location_id = None
    kind = "資源"
    quantity = 1000
    unit = "単位"
    text = ""
    start = None
    end = None


def build_location_resource(**overrides) -> dict:
    return LocationResourceFactory.build(**overrides)
