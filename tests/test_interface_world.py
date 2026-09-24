from ai.claude_code.interface.world.list_characters import ListCharacters
from ai.claude_code.interface.world.list_places import ListPlaces
from ai.claude_code.interface.world.search_ideas import SearchIdeas
from db.schema import Character, CharacterPlace, Idea, Location


def test_list_characters_includes_place(session):
    place = Location(name="村", kind="村", text="")
    session.add(place)
    session.flush()
    resident = Character(name="アル", text="村の子", sex="男", tone="です・ます", dialect="京言葉風")
    wanderer = Character(name="ベル", text="")
    session.add_all([resident, wanderer])
    session.flush()
    session.add(CharacterPlace(character_id=resident.id, location_id=place.id))
    session.commit()

    rows = ListCharacters().run()
    assert [row["name"] for row in rows] == ["アル", "ベル"]
    assert rows[0]["place_id"] == place.id
    assert rows[0]["text"] == "村の子"
    assert rows[0]["sex"] == "男"
    assert rows[0]["tone"] == "です・ます"
    assert rows[0]["dialect"] == "京言葉風"
    assert rows[1]["place_id"] is None


def test_list_places_filters_by_kind(session):
    planet = Location(name="ノウル", kind="星", text="")
    session.add(planet)
    session.flush()
    session.add(Location(name="村", kind="村", text="", parent_id=planet.id))
    session.commit()

    assert [row["name"] for row in ListPlaces().run()] == ["ノウル", "村"]
    villages = ListPlaces("村").run()
    assert [row["name"] for row in villages] == ["村"]
    assert villages[0]["parent_id"] == planet.id
    assert ListPlaces("町").run() == []


def test_search_ideas_matches_name_and_text(session):
    session.add_all([
        Idea(name="霊纏", kind="技術", text="霊を纏う技"),
        Idea(name="魔力灯り", kind="道具", text="魔力で灯す"),
    ])
    session.commit()

    rows = SearchIdeas("霊").run()
    assert [row["name"] for row in rows] == ["霊纏"]
    assert rows[0]["text"] == "霊を纏う技"
    assert [row["name"] for row in SearchIdeas("魔力灯り").run()] == ["魔力灯り"]
    assert SearchIdeas("鉄").run() == []
