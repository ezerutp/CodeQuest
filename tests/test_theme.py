from codequest.ui.theme import DARK, load_stylesheet


def test_all_style_tokens_resolve() -> None:
    qss = load_stylesheet(DARK)
    assert "${" not in qss
    assert DARK.bg in qss
