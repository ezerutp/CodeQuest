"""Lista de sugerencias de un CodeEditor editable, como la de VS Code.

El editor no sabe de dónde salen las sugerencias: pide (`requested`, con un número de petición) y
quien lo usa responde con `show()`. Mientras llegan, el estudiante puede seguir escribiendo; la
lista se filtra con lo escrito desde el inicio de la palabra y, si el servidor la recortó, se
vuelve a pedir con el texto nuevo.
"""

import logging
import re

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QStandardItem, QStandardItemModel, QTextCursor
from PySide6.QtWidgets import QCompleter, QPlainTextEdit

from codequest.core.lsp.models import CompletionList
from codequest.ui.icons import icon

log = logging.getLogger(__name__)

INSERT_ROLE = Qt.ItemDataRole.UserRole + 1
MAX_VISIBLE_ITEMS = 10
_IDENTIFIER_TAIL = re.compile(r"[A-Za-z0-9_$]*$")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_$]*")

# Tipo de sugerencia -> icono de ui/icons.py
KIND_ICONS = {
    "method": "method", "function": "method", "constructor": "method",
    "field": "field", "variable": "field", "property": "field",
    "class": "completion.class", "interface": "completion.class", "enum": "completion.class",
    "type_parameter": "completion.class", "module": "package",
    "enum_member": "completion.constant", "constant": "completion.constant",
    "keyword": "completion.keyword", "snippet": "completion.keyword",
}


class EditorCompleter(QObject):
    requested = Signal(int)  # número de petición: la respuesta debe traer el mismo

    def __init__(self, editor: QPlainTextEdit) -> None:
        super().__init__(editor)
        self._editor = editor
        self._model = QStandardItemModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setWidget(editor)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setModelSorting(QCompleter.ModelSorting.UnsortedModel)  # orden del servidor
        self._completer.setCompletionRole(INSERT_ROLE)
        self._completer.setMaxVisibleItems(MAX_VISIBLE_ITEMS)
        self._completer.activated[str].connect(self._insert)
        popup = self._completer.popup()
        popup.setObjectName("CompletionPopup")
        popup.installEventFilter(self)
        self._anchor: int | None = None  # posición donde empieza la palabra que se completa
        self._token = 0
        self._incomplete = False
        self._requested_prefix = ""
        self._refreshing = False

    # --- estado -------------------------------------------------------------------

    @property
    def is_visible(self) -> bool:
        return self._completer.popup().isVisible()

    @property
    def is_active(self) -> bool:
        """Hay una palabra en curso (con la lista visible o esperando sugerencias)."""
        return self._anchor is not None

    def items(self) -> list[str]:
        """Sugerencias que se muestran ahora, filtradas (texto que se insertaría)."""
        model = self._completer.completionModel()
        return [model.index(row, 0).data(INSERT_ROLE) for row in range(model.rowCount())]

    def prefix(self) -> str | None:
        """Lo escrito desde el inicio de la palabra; None si el cursor salió de ella."""
        if self._anchor is None:
            return None
        cursor = self._editor.textCursor()
        block = self._editor.document().findBlock(self._anchor)
        if cursor.position() < self._anchor or cursor.block() != block:
            return None
        text = block.text()[self._anchor - block.position():cursor.position() - block.position()]
        return text if _IDENTIFIER.fullmatch(text) else None

    # --- ciclo --------------------------------------------------------------------

    def request(self) -> None:
        """Pide sugerencias para la palabra que hay en el cursor (tras «.» o con Ctrl+Espacio)."""
        cursor = self._editor.textCursor()
        before = cursor.block().text()[:cursor.positionInBlock()]
        self._anchor = cursor.position() - len(_IDENTIFIER_TAIL.search(before).group())
        self._model.clear()
        self._hide_popup()
        self._send(self.prefix() or "")

    def show(self, token: int, result: CompletionList) -> None:
        """Respuesta a la petición `token`; se descarta si ya hay otra más nueva o el cursor se fue."""
        if token != self._token or self.prefix() is None:
            return
        self._model.clear()
        icons: dict[str, QIcon] = {}
        for item in result.items:
            entry = QStandardItem(item.label)
            entry.setData(item.insert_text, INSERT_ROLE)
            entry.setToolTip(item.detail)
            name = KIND_ICONS.get(item.kind, "completion.text")
            entry.setIcon(icons.setdefault(name, icon(name)))
            entry.setEditable(False)
            self._model.appendRow(entry)
        self._incomplete = result.is_incomplete
        self._refresh()

    def after_key(self) -> None:
        """Tras escribir o borrar: filtra la lista, la vuelve a pedir si estaba recortada o la cierra."""
        if self._anchor is None:
            return
        prefix = self.prefix()
        if prefix is None:
            self.hide()
            return
        if self._incomplete and prefix != self._requested_prefix:
            self._send(prefix)  # mientras llega, se sigue filtrando lo que ya hay
        self._refresh()

    def hide(self) -> None:
        self._anchor = None
        self._token += 1  # las respuestas pendientes ya no sirven
        self._hide_popup()

    # --- interno ------------------------------------------------------------------

    def _send(self, prefix: str) -> None:
        self._token += 1
        self._requested_prefix = prefix
        self.requested.emit(self._token)

    def _refresh(self) -> None:
        prefix = self.prefix()
        if prefix is None:
            return
        self._completer.setCompletionPrefix(prefix)
        if self._completer.completionCount() == 0:
            self._hide_popup()  # sin coincidencias; la palabra sigue activa por si llegan más
            return
        popup = self._completer.popup()
        popup.setFont(self._editor.font())
        rect = self._editor.cursorRect()
        rect.translate(self._editor.viewport().pos())  # cursorRect es relativo al viewport (sin el margen)
        rect.setWidth(min(max(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width() + 24,
                              260), 640))
        self._refreshing = True
        try:
            self._completer.complete(rect)
        finally:
            self._refreshing = False
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))

    def _hide_popup(self) -> None:
        self._refreshing = True
        try:
            self._completer.popup().hide()
        finally:
            self._refreshing = False

    def _insert(self, text: str) -> None:
        if self._anchor is None:
            return
        cursor = self._editor.textCursor()
        end = cursor.position()
        cursor.setPosition(self._anchor)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text)
        self._editor.setTextCursor(cursor)
        self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (API de Qt)
        # Escape, un clic fuera o elegir una opción cierran la lista: la palabra deja de completarse.
        # QCompleter oculta la lista antes de emitir `activated`: se espera a la vuelta del bucle.
        if event.type() == QEvent.Type.Hide and not self._refreshing:
            token = self._token
            QTimer.singleShot(0, lambda: self._on_popup_closed(token))
        return False

    def _on_popup_closed(self, token: int) -> None:
        if token == self._token and not self.is_visible:
            self._anchor = None
            self._token += 1
