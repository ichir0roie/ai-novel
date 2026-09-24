"""場所の輪郭 `polygon`: 解析、入口での確定・修正、md との往復、地図への描画。"""
import json
import os

import pytest

from DEM.ai.claude_code.interface.randomizer.commit_place import CommitPlace
from DEM.ai.claude_code.interface.randomizer.update_place import UpdatePlace
from DEM.ai.claude_code.interface.world.list_neighbors import ListNeighbors
from DEM.db.polygon import outer_ring, parse_polygon, polygon_center
from DEM.db.schema import Location
from DEM.tool.map.collect import collect_planets
from DEM.tool.map.layout import fit_frame
from DEM.tool.markdown.export_db import export_db
from DEM.tool.markdown.import_db import import_db

TRIANGLE = [[10, 20], [30, 20], [30, 40]]
CLOSED = {"type": "Polygon", "coordinates": [[[10.0, 20.0], [30.0, 20.0], [30.0, 40.0], [10.0, 20.0]]]}


def test_parse_polygon_closes_ring_and_normalizes():
    assert parse_polygon(TRIANGLE) == CLOSED
    assert parse_polygon([TRIANGLE]) == CLOSED
    assert parse_polygon(CLOSED) == CLOSED
    assert parse_polygon(json.dumps(CLOSED)) == CLOSED
    assert parse_polygon(None) is None and parse_polygon("") is None
    with_hole = parse_polygon([[[0, 0], [40, 0], [40, 40], [0, 40]], [[10, 10], [20, 10], [20, 20]]])
    assert len(with_hole["coordinates"]) == 2 and len(with_hole["coordinates"][1]) == 4


@pytest.mark.parametrize("bad", [
    [[10, 20], [30, 20]],                    # 三点未満
    [[10, 20, 5], [30, 20], [30, 40]],       # 三つ組
    [[200, 20], [30, 20], [30, 40]],         # 経度の範囲外
    {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
    {"type": "Polygon", "coordinates": []},
    "not json", 42,
])
def test_parse_polygon_rejects(bad):
    with pytest.raises(ValueError):
        parse_polygon(bad)


def test_outer_ring_and_center():
    assert outer_ring(CLOSED) == [[10.0, 20.0], [30.0, 20.0], [30.0, 40.0]]
    assert polygon_center(CLOSED) == pytest.approx((70 / 3, 80 / 3))


def test_commit_and_update_place_store_polygon(session):
    created = CommitPlace({"name": "国", "kind": "国", "text": "", "polygon": TRIANGLE}).run()
    assert created["polygon"] == CLOSED
    assert session.get(Location, created["id"]).polygon == CLOSED

    updated = UpdatePlace({"id": created["id"], "polygon": None}).run()
    assert updated["polygon"] is None
    session.expire_all()
    assert session.get(Location, created["id"]).polygon is None
    assert session.query(Location).filter(Location.polygon.is_(None)).count() == 1

    with pytest.raises(ValueError, match="三つ以上"):
        UpdatePlace({"id": created["id"], "polygon": [[0, 0], [1, 1]]}).run()


def test_polygon_round_trips_through_markdown(session, tmp_path):
    planet = Location(name="星", kind="星", text="", directory_path="星")
    session.add(planet)
    session.flush()
    session.add(Location(name="大陸", kind="大陸", text="本文", parent_id=planet.id,
                         location_planet=planet.id, polygon=TRIANGLE))
    session.commit()
    root = str(tmp_path / "worlds")
    export_db(root)

    md_path = next(os.path.join(d, f) for d, _, fs in os.walk(os.path.join(root, "location"))
                   for f in fs if f.endswith(".md") and "大陸" in open(os.path.join(d, f), encoding="utf-8").read())
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    assert '"polygon": {\n    "type": "Polygon",' in content

    content = content.replace("40.0", "45.0")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    import_db(root)
    session.expire_all()
    row = session.query(Location).filter_by(name="大陸").one()
    assert row.polygon["coordinates"][0][2] == [30.0, 45.0]


@pytest.fixture
def outlined(session):
    """輪郭だけの大陸と、輪郭も点も持つ国、点だけの町を置いた星。"""
    planet = Location(name="星", kind="星", text="", area=510_072_000, directory_path="星")
    session.add(planet)
    session.flush()
    continent = Location(name="大陸", kind="大陸", text="", parent_id=planet.id, location_planet=planet.id,
                         polygon=[[-20, -10], [60, -10], [60, 50], [-20, 50]])
    session.add(continent)
    session.flush()
    country = Location(name="国", kind="国", text="", parent_id=continent.id, location_planet=planet.id,
                       location_longitude=20, location_latitude=20, polygon=TRIANGLE)
    town = Location(name="町", kind="町", text="", parent_id=continent.id, location_planet=planet.id,
                    location_longitude=5, location_latitude=5)
    session.add_all([country, town])
    session.commit()
    return {"planet": planet.id, "continent": continent.id, "country": country.id, "town": town.id}


def test_collect_separates_points_and_shapes(session, outlined):
    [entry] = collect_planets(session)
    assert [p["name"] for p in entry["points"]] == ["国", "町"]
    assert [p["name"] for p in entry["shapes"]] == ["大陸", "国"]
    assert entry["shapes"][0]["lon"] is None and entry["shapes"][0]["polygon"]["type"] == "Polygon"
    assert entry["points"][1]["polygon"] is None

    frame = fit_frame(entry["points"], entry["shapes"])
    assert (frame.lon_min, frame.lon_max, frame.lat_min, frame.lat_max) == (-30, 70, -20, 60)


def test_list_neighbors_ignores_shape_only_places(outlined):
    result = ListNeighbors(outlined["town"]).run()
    assert [n["name"] for n in result["neighbors"]] == ["国"]
    assert result["neighbors"][0]["polygon"] == CLOSED


def test_export_draws_polygons(outlined, tmp_path):
    root = str(tmp_path / "worlds")
    export_db(root)

    with open(os.path.join(root, "location", "星", f"{outlined['planet']}_map.svg"), encoding="utf-8") as f:
        svg = f.read()
    assert svg.count('<g class="shape">') == 2
    assert 'fill-rule="evenodd"' in svg and "薄い面は輪郭" in svg
    # 点を持たない大陸だけ、面の真ん中に名を置く
    assert svg.count('font-weight="bold" fill="#') == 1 and ">大陸</text>" in svg
    assert "星 (星)" in svg  # 大陸の親(星)も凡例に並ぶ

    with open(os.path.join(root, "maps", "map.html"), encoding="utf-8") as f:
        html = f.read()
    assert '"shapes": [' in html and '"type": "Polygon"' in html
    assert "function shapePath" in html


def test_export_with_only_shapes_still_draws_planet(session, tmp_path):
    planet = Location(name="星", kind="星", text="")
    session.add(planet)
    session.flush()
    session.add(Location(name="大陸", kind="大陸", text="", parent_id=planet.id, location_planet=planet.id,
                         polygon=TRIANGLE))
    session.commit()
    export_db(str(tmp_path / "worlds"))
    with open(os.path.join(str(tmp_path / "worlds"), "location", f"{planet.id}_map.svg"), encoding="utf-8") as f:
        assert ">大陸</text>" in f.read()
