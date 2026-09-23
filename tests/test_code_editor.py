"""Tests del CodeEditor con un QApplication offscreen (sin ventana)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QTextCursor, QTextFormat  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from codequest.ui.widgets.code_editor import CodeEditor  # noqa: E402

CODE = "public class A {\n    void m() {\n        run();\n    }\n}"


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def highlighted_block_numbers(editor: CodeEditor) -> list[int]:
    return [s.cursor.blockNumber() for s in editor.extraSelections()
            if s.format.property(QTextFormat.Property.FullWidthSelection)]


def test_highlight_uses_real_file_line_numbers(qapp: QApplication) -> None:
    editor = CodeEditor()
    editor.set_code(CODE, first_line=40)

    editor.highlight_lines([41, 42])

    # Las líneas 41-42 del archivo son los bloques 1-2 del fragmento.
    assert highlighted_block_numbers(editor) == [1, 2]
    assert editor.textCursor().blockNumber() == 1  # hizo scroll a la primera


def test_highlight_ignores_lines_outside_snippet(qapp: QApplication) -> None:
    editor = CodeEditor()
    editor.set_code(CODE, first_line=10)

    editor.highlight_lines([1, 999])

    assert highlighted_block_numbers(editor) == []


def test_set_code_resets_highlights(qapp: QApplication) -> None:
    editor = CodeEditor()
    editor.set_code(CODE)
    editor.highlight_lines([2])

    editor.set_code("int x;")

    assert highlighted_block_numbers(editor) == []


def test_read_only_blocks_typing(qapp: QApplication) -> None:
    editor = CodeEditor(read_only=True)
    editor.set_code(CODE)

    QTest.keyClicks(editor, "zzz")

    assert editor.code() == CODE


def test_editable_mode_auto_indents_after_brace(qapp: QApplication) -> None:
    editor = CodeEditor(read_only=False)
    editor.set_code("    void m() {")
    editor.moveCursor(QTextCursor.MoveOperation.End)

    QTest.keyClick(editor, Qt.Key.Key_Return)
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    QTest.keyClicks(editor, "x();")

    assert editor.code() == "    void m() {\n            x();"


def test_line_number_gutter_grows_with_digits(qapp: QApplication) -> None:
    editor = CodeEditor()
    editor.set_code("a")
    narrow = editor.line_number_width()

    editor.set_code("a", first_line=12345)

    assert editor.line_number_width() > narrow
