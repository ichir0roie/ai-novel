"""語を直す・消す入口。上位の語の付け替えと、下位の語が残っている語の削除を検める。"""
import pytest

from DEM.ai.claude_code.interface._base import UnknownFieldError, UnknownRecordError
from DEM.ai.claude_code.interface.randomizer.delete_term import DeleteTerm
from DEM.ai.claude_code.interface.randomizer.update_term import UpdateTerm
from DEM.db.schema import Location, Term


@pytest.fixture
def terms(session):
    world = Location(name="世界線", kind="世界線", text="")
    session.add(world)
    session.flush()
    parent = Term(name="崩壊時代", kind="時代", restrict_world_id=world.id, text="時代")
    session.add(parent)
    session.flush()
    child = Term(name="崩壊年", kind="呼称", parent_term_id=parent.id, text="呼称")
    session.add(child)
    session.commit()
    return {"world": world.id, "parent": parent.id, "child": child.id}


def test_update_changes_given_columns(session, terms):
    result = UpdateTerm({"id": terms["child"], "kind": "概念", "text": "直した"}).run()

    assert result["kind"] == "概念" and result["text"] == "直した"
    record = session.get(Term, terms["child"])
    assert record.name == "崩壊年" and record.parent_term_id == terms["parent"]


def test_update_repoints_parent(session, terms):
    other = Term(name="崩壊時代", kind="時代", text="時代")
    session.add(other)
    session.commit()

    UpdateTerm({"id": terms["child"], "parent_term_id": other.id}).run()
    assert session.get(Term, terms["child"]).parent_term_id == other.id


def test_update_rejects_bad_input(session, terms):
    with pytest.raises(ValueError, match="id は必須"):
        UpdateTerm({"kind": "概念"}).run()
    with pytest.raises(ValueError, match="id=999"):
        UpdateTerm({"id": 999, "kind": "概念"}).run()
    with pytest.raises(UnknownRecordError, match="parent_term_id=999"):
        UpdateTerm({"id": terms["child"], "parent_term_id": 999}).run()
    with pytest.raises(ValueError, match="自分自身"):
        UpdateTerm({"id": terms["child"], "parent_term_id": terms["child"]}).run()
    with pytest.raises(UnknownFieldError):
        UpdateTerm({"id": terms["child"], "read": "ご"}).run()


def test_delete_removes_term(session, terms):
    data = DeleteTerm(terms["child"]).run()

    assert data == {"id": terms["child"], "name": "崩壊年", "kind": "呼称"}
    session.expire_all()
    assert session.get(Term, terms["child"]) is None
    assert session.get(Term, terms["parent"]) is not None


def test_delete_keeps_term_with_children(session, terms):
    with pytest.raises(ValueError, match="下位の語が残っている"):
        DeleteTerm(terms["parent"]).run()
    with pytest.raises(UnknownRecordError, match="term_id=999"):
        DeleteTerm(999).run()
    session.expire_all()
    assert session.get(Term, terms["parent"]) is not None
