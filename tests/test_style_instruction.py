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


@pytest.mark.parametrize("target", ["episode", "story", "event", "term"])
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


def test_episode_prompt_embeds_the_episode_style():
    from DEM.ai.claude_code import story_writer

    assert style.EPISODE_STYLE_INSTRUCTION in story_writer._SYSTEM_PROMPT
