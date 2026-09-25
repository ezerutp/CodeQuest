"""Lista de sugerencias del editor y su conexión con «Corrige el código» (QApplication offscreen)."""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QTextCursor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from codequest.core.lsp.models import CompletionItem, CompletionList  # noqa: E402
from codequest.ui.widgets import CodeEditor  # noqa: E402

STATUSES = CompletionList(tuple(CompletionItem(f"{name} : HttpStatus", name, "enum_member")
                                for name in ("NO_CONTENT", "NOT_FOUND", "OK")))


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _editor(text: str) -> tuple[CodeEditor, list[int]]:
    editor = CodeEditor(read_only=False)
    editor.set_completion_enabled(True)
    requests: list[int] = []
    editor.completion_requested.connect(requests.append)
    editor.resize(600, 200)
    editor.show()
    editor.set_code(text)
    editor.moveCursor(QTextCursor.MoveOperation.End)
    editor.setFocus()
    return editor, requests


def _type(editor: CodeEditor, text: str) -> None:
    for char in text:
        QTest.keyClicks(editor, char)


def test_dot_requests_and_typing_filters_then_enter_inserts(qapp: QApplication) -> None:
    editor, requests = _editor("@ResponseStatus(HttpStatus")
    _type(editor, ".")
    assert len(requests) == 1 and editor.completer.is_active
    editor.show_completions(requests[0], STATUSES)
    assert editor.completer.is_visible and editor.completer.items() == ["NO_CONTENT", "NOT_FOUND", "OK"]
    _type(editor, "no")  # sin distinguir mayúsculas
    assert editor.completer.items() == ["NO_CONTENT", "NOT_FOUND"]
    _type(editor, "t")
    assert editor.completer.items() == ["NOT_FOUND"] and len(requests) == 1  # lista completa: no se vuelve a pedir
    QTest.keyClick(editor.completer._completer.popup(), Qt.Key.Key_Return)
    assert editor.code() == "@ResponseStatus(HttpStatus.NOT_FOUND"
    assert not editor.completer.is_active and not editor.completer.is_visible
    editor.hide()


def test_stale_answers_are_ignored_and_leaving_the_word_closes(qapp: QApplication) -> None:
    editor, requests = _editor("x = HttpStatus")
    _type(editor, ".")
    _type(editor, ".")  # otra petición: la primera queda vieja
    editor.show_completions(requests[0], STATUSES)
    assert not editor.completer.is_visible
    editor.show_completions(requests[1], STATUSES)
    assert editor.completer.is_visible
    _type(editor, " ")
    assert not editor.completer.is_active and not editor.completer.is_visible
    editor.show_completions(requests[1], STATUSES)  # llega tarde: ya no se muestra
    assert not editor.completer.is_visible
    editor.hide()


def test_escape_closes_and_ctrl_space_completes_the_current_word(qapp: QApplication) -> None:
    editor, requests = _editor("categoriaService.eli")
    QTest.keyClick(editor, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    assert len(requests) == 1 and editor.completer.prefix() == "eli"
    methods = CompletionList((CompletionItem("eliminar(Long id) : void", "eliminar", "method"),
                              CompletionItem("equals(Object o) : boolean", "equals", "method")))
    editor.show_completions(requests[0], methods)
    assert editor.completer.items() == ["eliminar"]
    QTest.keyClick(editor.completer._completer.popup(), Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not editor.completer.is_active
    _type(editor, "m")
    assert editor.code() == "categoriaService.elim" and not editor.completer.is_visible
    editor.hide()


def test_incomplete_lists_are_requested_again_while_typing(qapp: QApplication) -> None:
    editor, requests = _editor("HttpStatus")
    _type(editor, ".")
    editor.show_completions(requests[0], CompletionList(STATUSES.items, is_incomplete=True))
    _type(editor, "N")
    assert len(requests) == 2 and editor.completer.items() == ["NO_CONTENT", "NOT_FOUND"]  # filtra mientras
    editor.show_completions(requests[1], CompletionList(STATUSES.items[:1]))
    assert editor.completer.items() == ["NO_CONTENT"]
    _type(editor, "O")
    assert len(requests) == 2
    editor.hide()


def test_disabled_or_read_only_editors_do_not_suggest(qapp: QApplication) -> None:
    editor, requests = _editor("a")
    editor.set_completion_enabled(False)
    _type(editor, ".")
    assert requests == [] and editor.completer is None
    editor.set_completion_enabled(True)
    editor.completer.request()
    editor.set_read_only(True)
    assert not editor.completer.is_active
    editor.hide()


def test_fix_code_view_sends_the_whole_file_in_memory(qapp: QApplication) -> None:
    from test_fix_code_view import CODE, FILE, _session, _view

    calls: list[tuple[str, str, int, int]] = []

    def complete(path: str, text: str, line: int, column: int) -> CompletionList:
        calls.append((path, text, line, column))
        return STATUSES

    view = _view()
    view._complete = complete
    view.show()
    view.start(_session(), None)
    view.set_language_server_ready(True)
    assert "Ctrl+Espacio" in view._hint.text()
    editor = view._editor
    editor.set_code(CODE.replace("return service.find(id);", "return HttpStatus"), first_line=2)
    cursor = editor.textCursor()
    cursor.setPosition(editor.code().index("HttpStatus") + len("HttpStatus"))
    editor.setTextCursor(cursor)
    _type(editor, ".")
    deadline = time.monotonic() + 5
    while not editor.completer.is_visible and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    path, text, line, column = calls[0]
    assert path == "A.java" and line == 3 and column == len("        return HttpStatus.")
    assert text.split("\n")[line] == "        return HttpStatus." and text.startswith("class UserController {\n")
    assert text.endswith("\n}\n") and FILE.count("\n") == text.count("\n")
    assert editor.completer.items() == ["NO_CONTENT", "NOT_FOUND", "OK"]
    view.set_language_server_ready(False)
    assert "Ctrl+Espacio" not in view._hint.text() and editor.completer is None
    view.shutdown()
    view.hide()
