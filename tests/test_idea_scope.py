"""アイデアを引く範囲。配下だけでなく、属する星・世界線まで親方向へのぼって当てる。"""
import pytest

from ai.claude_code.interface.story import _rows
from data_access_logic.query import common_query
from db.schema import Idea, Location


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


def add_idea(session, name, **restrict):
    record = Idea(name=name, kind="概念", text="", **restrict)
    session.add(record)
    session.flush()
    return record.id


def test_scope_holds_both_descendants_and_ancestors(session, places):
    ids = common_query.idea_scope_ids(session, places["planet"])

    assert places["planet"] in ids
    assert places["country"] in ids
    assert places["world"] in ids


def test_world_wide_idea_reaches_the_brief(session, places):
    add_idea(session, "世界線のアイデア", restrict_world_id=places["world"])
    session.commit()

    names = [idea["name"] for idea in _rows.brief(session, places["planet"], "0001/01/01")["ideas"]]

    assert names == ["世界線のアイデア"]


def test_planet_and_descendant_ideas_reach_the_brief(session, places):
    add_idea(session, "星のアイデア", restrict_planet_id=places["planet"])
    add_idea(session, "国のアイデア", restrict_place_id=places["country"])
    session.commit()

    names = [idea["name"] for idea in _rows.brief(session, places["planet"], "0001/01/01")["ideas"]]

    assert sorted(names) == ["国のアイデア", "星のアイデア"]


def test_idea_without_restriction_is_left_out(session, places):
    add_idea(session, "掛かる先の無いアイデア")
    session.commit()

    assert _rows.brief(session, places["planet"], "0001/01/01")["ideas"] == []


def test_idea_of_another_branch_is_left_out(session, places):
    other = Location(name="別の星", kind="星", parent_id=places["world"], text="")
    session.add(other)
    session.flush()
    add_idea(session, "別の星のアイデア", restrict_planet_id=other.id)
    session.commit()

    assert _rows.brief(session, places["planet"], "0001/01/01")["ideas"] == []
