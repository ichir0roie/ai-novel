from ai.instructions.naming import fill_name_placeholder


def test_placeholder_is_filled_with_the_name():
    assert fill_name_placeholder("【名前】は帳面を開く。[ 名前 ]も", "シャヒル") == "シャヒルは帳面を開く。シャヒルも"


def test_name_left_inside_the_placeholder_brackets_is_unwrapped():
    assert fill_name_placeholder("【シャヒル】は書き残す。【 シャヒル 】", "シャヒル") == "シャヒルは書き残す。シャヒル"


def test_other_brackets_are_kept():
    text = "【関所】で(1628〜、シャヒル)と書く。【ガシム】"
    assert fill_name_placeholder(text, "シャヒル") == text
