import pytest

from ai.claude_code import fact_checker
from ai.instructions import sensitive
from ai.time_keeper import idea_search, meme


@pytest.mark.parametrize("prompt", [meme._SYSTEM_PROMPT, idea_search._SYSTEM_PROMPT])
def test_meme_and_idea_prompts_keep_bio_topics_abstract(prompt):
    assert sensitive.BIO_ABSTRACTION_INSTRUCTION in prompt


def test_fact_check_prompt_keeps_bio_topics_abstract():
    assert sensitive.FACT_CHECK_BIO_INSTRUCTION in fact_checker._SYSTEM_PROMPT


def test_fact_check_instruction_includes_the_shared_one():
    assert sensitive.BIO_ABSTRACTION_INSTRUCTION in sensitive.FACT_CHECK_BIO_INSTRUCTION


@pytest.mark.parametrize("prompt", [meme._SYSTEM_PROMPT, idea_search._SYSTEM_PROMPT, fact_checker._SYSTEM_PROMPT])
def test_bio_instruction_sits_before_the_answer_format(prompt):
    assert prompt.index(sensitive.BIO_ABSTRACTION_INSTRUCTION) < prompt.index("JSON で答えてください")
