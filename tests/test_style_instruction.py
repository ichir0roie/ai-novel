"""文体の定数(共通 + 対象ごと)の組み立て。"""
import pytest

from DEM.ai.instructions import style


def test_text_joins_base_and_extracted():
    instruction = style.StyleInstruction(base="土台", extracted="特徴")
    assert instruction.text == "土台\n特徴"


def test_text_is_base_only_while_extracted_is_empty():
    assert style.StyleInstruction(base="土台").text == "土台"


def test_text_is_empty_without_both():
    assert style.StyleInstruction().text == ""


@pytest.mark.parametrize("target", ["episode", "event_novel", "story", "event", "term"])
def test_style_instruction_has_shared_and_own_base(target):
    text = style.style_instruction(target)
    assert style.SHARED_STYLE_BASE.strip() in text
    assert style.STYLE_INSTRUCTIONS[target].base in text


def test_style_instruction_rejects_unknown_target():
    with pytest.raises(ValueError):
        style.style_instruction("character")


def test_episode_style_states_the_blank_line_rule():
    base = style.EPISODE_STYLE_BASE
    assert "空行は、言動の主体が変わるとき" in base
    assert "改行だけで続ける" in base
    assert "一話に数回まで" in base


def test_event_novel_is_a_third_of_an_episode():
    assert style.EVENT_NOVEL_TARGET_LETTERS == (1700, 2700)
    text = style.EVENT_NOVEL_STYLE_INSTRUCTION
    assert "出来事一件は1700〜2700字" in text
    assert "一話は5000〜8000字" not in text
    assert "種(key)" not in text


def test_event_novel_shares_the_episode_novel_style():
    assert style.NOVEL_STYLE_BASE in style.EPISODE_STYLE_BASE
    assert style.NOVEL_STYLE_BASE in style.EVENT_NOVEL_STYLE_INSTRUCTION
    assert style.EPISODE_STYLE_EXTRACTED in style.EVENT_NOVEL_STYLE_INSTRUCTION


def test_episode_style_keeps_its_length_rule():
    base = style.EPISODE_STYLE_BASE
    assert "一話は5000〜8000字。4〜6個の場面に分け、一場面は1200〜1600字を目安にする。" in base
    assert base.endswith("種(key)に場面が足りないときは、足りないぶんを場面として立ててから書く。")


def test_episode_prompt_embeds_the_episode_style():
    from DEM.ai.claude_code import story_writer

    assert style.EPISODE_STYLE_INSTRUCTION in story_writer._SYSTEM_PROMPT


def test_episode_style_carries_the_extracted_habits():
    extracted = style.EPISODE_STYLE_EXTRACTED
    assert "話し言葉" in extracted
    assert "「？」" in extracted and "「！」" in extracted and "「…」" in extracted
    assert extracted in style.EPISODE_STYLE_INSTRUCTION


def test_shared_extracted_leaves_the_umeru_wording_alone():
    """「欄を埋める」はピリムの癖として残すので、共通の言い換えからは外す。"""
    assert "欄を埋める" not in style.SHARED_STYLE_EXTRACTED
    assert "欄を埋める" in style.EPISODE_STYLE_EXTRACTED


def test_shared_extracted_reaches_every_target():
    for target in style.STYLE_INSTRUCTIONS:
        assert style.SHARED_STYLE_EXTRACTED in style.style_instruction(target)


def test_shared_extracted_separates_the_fairy_from_the_lamp():
    """妖精は「光」で書き、「灯り」は魔力灯りと明かりに取っておく。"""
    extracted = style.SHARED_STYLE_EXTRACTED
    assert "体を持たない妖精が現れる場面は「光」" in extracted
    assert "「灯り」は手のひらの魔力灯り" in extracted
