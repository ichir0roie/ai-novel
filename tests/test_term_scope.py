"""語を引く範囲。配下だけでなく、属する星・世界線まで親方向へのぼって当てる。"""
import pytest

from DEM.ai.claude_code.interface.story import _rows
from DEM.data_access_logic.query import common_query
from DEM.db.schema import Location, Term


@pytest.fixture
def places(session):
    world = Location(name="世界線", kind="世界線", text="")
    session.add(world)
    session.flush()
    planet = Location(name="星", kind="星", parent_id=world.id, text="")
    session.add(planet)
    session.flush()
    country = Location(name="国", kind="国", parent_id=planet.id, text="")
    session.add(country)
    session.flush()
    return {"world": world.id, "planet": planet.id, "country": country.id}


def add_term(session, name, **restrict):
    record = Term(name=name, kind="概念", text="", **restrict)
    session.add(record)
    session.flush()
    return record.id


def test_scope_holds_both_descendants_and_ancestors(session, places):
    ids = common_query.term_scope_ids(session, places["planet"])

    assert places["planet"] in ids
    assert places["country"] in ids
    assert places["world"] in ids


def test_world_wide_term_reaches_the_brief(session, places):
    add_term(session, "世界線の語", restrict_world_id=places["world"])
    session.commit()

    names = [term["name"] for term in _rows.brief(session, places["planet"], "0001/01/01")["terms"]]

    assert names == ["世界線の語"]


def test_planet_and_descendant_terms_reach_the_brief(session, places):
    add_term(session, "星の語", restrict_planet_id=places["planet"])
    add_term(session, "国の語", restrict_place_id=places["country"])
    session.commit()

    names = [term["name"] for term in _rows.brief(session, places["planet"], "0001/01/01")["terms"]]

    assert sorted(names) == ["国の語", "星の語"]


def test_term_without_restriction_is_left_out(session, places):
    add_term(session, "掛かる先の無い語")
    session.commit()

    assert _rows.brief(session, places["planet"], "0001/01/01")["terms"] == []


def test_term_of_another_branch_is_left_out(session, places):
    other = Location(name="別の星", kind="星", parent_id=places["world"], text="")
    session.add(other)
    session.flush()
    add_term(session, "別の星の語", restrict_planet_id=other.id)
    session.commit()

    assert _rows.brief(session, places["planet"], "0001/01/01")["terms"] == []
