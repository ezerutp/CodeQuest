"""Editor de código reutilizable: números de línea, resaltado y modo solo lectura/editable."""

import weakref
from collections.abc import Iterable, Mapping

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from codequest.ui.theme import current_palette
from codequest.ui.widgets.java_highlighter import JavaHighlighter
from codequest.ui.widgets.style_utils import repolish

MONOSPACE_FAMILIES = ("JetBrains Mono", "Fira Code", "Cascadia Code", "Source Code Pro", "Noto Sans Mono",
                      "DejaVu Sans Mono", "Consolas", "Menlo")
INDENT = "    "
DEFAULT_FONT_SIZE = 11

_font_size = DEFAULT_FONT_SIZE
_editors: "weakref.WeakSet[CodeEditor]" = weakref.WeakSet()


def set_editor_font_size(point_size: int) -> None:
    """Cambia el tamaño de letra de todos los editores (abiertos y futuros)."""
    global _font_size
    _font_size = point_size
    for editor in list(_editors):
        editor.apply_font_size(point_size)


def monospace_font(point_size: int = 11) -> QFont:
    available = set(QFontDatabase.families())
    family = next((f for f in MONOSPACE_FAMILIES if f in available), None)
    font = QFont(family) if family else QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(point_size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


class _LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        self._editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """QPlainTextEdit con aspecto de IDE.

    `first_line` permite mostrar un fragmento con la numeración real del archivo:
    si el fragmento empieza en la línea 42, la primera línea visible se numera 42.
    Todas las APIs públicas usan esa numeración.
    """

    def __init__(self, parent: QWidget | None = None, read_only: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("CodeEditor")
        self._palette = current_palette()
        self._first_line = 1
        self._highlighted: dict[int, str] = {}  # línea real -> color de fondo

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._highlighter = JavaHighlighter(self.document(), self._palette)

        self._gutter = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._refresh_selections)
        self.apply_font_size(_font_size)
        self.set_read_only(read_only)
        _editors.add(self)

    def apply_font_size(self, point_size: int) -> None:
        self.setFont(monospace_font(point_size))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * len(INDENT))
        self._update_gutter_width()
        self._gutter.setFont(self.font())
        self.updateGeometry()

    # --- API pública ------------------------------------------------------------

    def set_code(self, text: str, first_line: int = 1) -> None:
        self._first_line = first_line
        self._highlighted.clear()
        self.setPlainText(text)
        self._update_gutter_width()
        self.moveCursor(QTextCursor.MoveOperation.Start)
        self._refresh_selections()

    def code(self) -> str:
        return self.toPlainText()

    @property
    def first_line(self) -> int:
        return self._first_line

    def set_read_only(self, read_only: bool) -> None:
        self.setReadOnly(read_only)
        # El cursor sigue siendo útil en solo lectura: permite seleccionar y copiar.
        flags = Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        if not read_only:
            flags |= Qt.TextInteractionFlag.TextEditorInteraction
        self.setTextInteractionFlags(flags)
        repolish(self)  # el QSS usa [readOnly=...]
        self._refresh_selections()

    def highlight_lines(self, lines: Iterable[int], scroll: bool = True) -> None:
        """Resalta líneas (numeración real del archivo) y opcionalmente las hace visibles."""
        self.mark_lines(dict.fromkeys(lines, self._palette.editor_highlight_line), scroll=scroll)

    def mark_lines(self, marks: Mapping[int, str], scroll: bool = False) -> None:
        """Como `highlight_lines`, pero con un color por línea (p. ej. acierto en verde, fallo en rojo)."""
        self._highlighted = dict(marks)
        self._refresh_selections()
        if scroll and self._highlighted:
            self.scroll_to_line(min(self._highlighted))

    def cursor_line(self) -> int:
        """Línea (numeración real) donde está el cursor: en solo lectura, la última que se pulsó."""
        return self.textCursor().blockNumber() + self._first_line

    def clear_highlights(self) -> None:
        self.highlight_lines((), scroll=False)

    def scroll_to_line(self, line: int) -> None:
        block = self.document().findBlockByNumber(line - self._first_line)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        # Deja la línea en el tercio superior en vez de pegada al borde.
        self.centerCursor()

    # --- números de línea ---------------------------------------------------------

    def line_number_width(self) -> int:
        last = self._first_line + max(1, self.blockCount()) - 1
        digits = max(3, len(str(last)))
        return 20 + self.fontMetrics().horizontalAdvance("9") * digits

    def paint_line_numbers(self, event: QPaintEvent) -> None:
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor(self._palette.editor_gutter))
        painter.setFont(self.font())
        current = self.textCursor().blockNumber()
        width = self._gutter.width() - 12
        height = self.fontMetrics().height()

        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = block.blockNumber() + self._first_line
                is_cursor_line = block.blockNumber() == current and not self.isReadOnly()
                active = is_cursor_line or number in self._highlighted
                painter.setPen(QColor(self._palette.editor_line_number_active if active
                                      else self._palette.editor_line_number))
                painter.drawText(0, top, width, height, Qt.AlignmentFlag.AlignRight, str(number))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())

    def _update_gutter_width(self, *_: object) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        area = self.contentsRect()
        self._gutter.setGeometry(QRect(area.left(), area.top(), self.line_number_width(), area.height()))

    # --- resaltado de líneas --------------------------------------------------------

    def _refresh_selections(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        for line, color in sorted(self._highlighted.items()):
            block = self.document().findBlockByNumber(line - self._first_line)
            if block.isValid():
                selections.append(self._line_selection(QTextCursor(block), color))
        if not self.isReadOnly() and not self._highlighted:
            selections.append(self._line_selection(self.textCursor(), self._palette.editor_current_line))
        self.setExtraSelections(selections)
        self._gutter.update()

    @staticmethod
    def _line_selection(cursor: QTextCursor, color: str) -> QTextEdit.ExtraSelection:
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(color))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        cursor.clearSelection()
        selection.cursor = cursor
        return selection

    # --- edición --------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self.isReadOnly():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Tab and not event.modifiers():
            self.insertPlainText(INDENT)
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Mantiene la sangría de la línea actual (y la aumenta tras "{").
            line = self.textCursor().block().text()
            indent = line[:len(line) - len(line.lstrip())]
            if line.rstrip().endswith("{"):
                indent += INDENT
            super().keyPressEvent(event)
            self.insertPlainText(indent)
            return
        super().keyPressEvent(event)
