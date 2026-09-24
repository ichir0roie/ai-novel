from data_access_logic.query.base import *


def load_location_story(s: Session, location_id: int, time: Stamp):
    """`location_id` とその祖先に掛かる、`time` に有効な作品(`Story`)。上位の場所のものから順。"""
    location = s.get(Location, location_id)
    if location is None:
        raise ValueError()

    location_ids = [location.id]
    while location.parent_id is not None:
        location = s.get(Location, location.parent_id)
        if location is None:
            break
        location_ids.append(location.id)

    depth = {lid: i for i, lid in enumerate(reversed(location_ids))}
    stories = s.scalars(
        select(Story).where(
            Story.place_id.in_(location_ids),
            story_time_condition(time),
        ).order_by(Story.id)
    ).all()
    return sorted(stories, key=lambda story: depth[story.place_id])


def join_story_text(stories: list[Story]) -> str:
    """作品の本文を、渡された順のまま一つのテキストにつなげる。"""
    return "\n\n".join(story.text for story in stories if story.text)


def load_location_story_text(s: Session, location_id: int, time: Stamp) -> str:
    return join_story_text(load_location_story(s, location_id, time))
