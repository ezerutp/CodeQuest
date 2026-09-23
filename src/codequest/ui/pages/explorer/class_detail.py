"""Ficha de una clase: tipo, anotaciones, miembros y su código real."""

import logging
from collections.abc import Callable
from pathlib import PurePosixPath

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from codequest.core.analysis.java.models import (
    JavaClass,
    JavaField,
    JavaMethod,
    TypeKind,
)
from codequest.core.analysis.package_tree import display_name
from codequest.core.analysis.roles import ComponentRole
from codequest.core.analysis.snippets import CodeSnippet
from codequest.ui.formatting import ROLE_LABELS
from codequest.ui.icons import icon, icon_label
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, Chip, CodeEditor, heading, mono, muted

log = logging.getLogger(__name__)

SourceLoader = Callable[[JavaClass], CodeSnippet]
_LINES_ROLE = Qt.ItemDataRole.UserRole
_MAX_ANNOTATION_CHIPS = 6


class ClassDetail(QWidget):
    practice_requested = Signal(object)  # JavaClass

    def __init__(self, load_source: SourceLoader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_source = load_source
        self._class: JavaClass | None = None

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_empty())
        self._stack.addWidget(self._build_content())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    # --- construcción -------------------------------------------------------

    def _build_empty(self) -> QWidget:
        card = Card(padding=40)
        card.body.addStretch(1)
        card.body.addWidget(icon_label("project", size=40, color=current_palette().text_subtle), 0,
                            Qt.AlignmentFlag.AlignHCenter)
        hint = muted("Selecciona una clase en el árbol para ver qué hace y cómo está construida.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.body.addWidget(hint)
        card.body.addStretch(1)
        return card

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = Card(padding=18)
        header.body.setSpacing(8)
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(6)
        self._name = heading("", level=2, word_wrap=False)
        self._chips = QHBoxLayout()
        self._chips.setSpacing(6)
        chips_holder = QWidget()
        chips_holder.setLayout(self._chips)
        self._chips.setContentsMargins(0, 0, 0, 0)
        self._location = mono("")
        title_box.addWidget(self._name)
        title_box.addWidget(chips_holder)
        title_box.addWidget(self._location)
        top.addLayout(title_box, 1)

        self._practice = QPushButton("Practicar esta clase")
        self._practice.setIcon(icon("practice", color="#ffffff", color_on="#ffffff"))
        self._practice.setIconSize(QSize(18, 18))
        self._practice.setProperty("variant", "primary")
        self._practice.clicked.connect(lambda: self._class and self.practice_requested.emit(self._class))
        top.addWidget(self._practice, 0, Qt.AlignmentFlag.AlignTop)
        header.body.addLayout(top)

        self._annotations = QHBoxLayout()
        self._annotations.setSpacing(6)
        self._annotations.setContentsMargins(0, 0, 0, 0)
        self._annotations_holder = QWidget()
        self._annotations_holder.setLayout(self._annotations)
        header.body.addWidget(self._annotations_holder)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self._members = QTreeWidget()
        self._members.setHeaderHidden(True)
        self._members.setIndentation(0)
        self._members.setRootIsDecorated(False)
        self._members.setIconSize(QSize(15, 15))
        self._members.setMinimumWidth(200)
        self._members.currentItemChanged.connect(self._on_member_selected)
        members_card = Card(padding=10)
        members_card.body.addWidget(self._members)
        splitter.addWidget(members_card)

        code_box = QWidget()
        code_layout = QVBoxLayout(code_box)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(6)
        self._file_label = QLabel()
        self._file_label.setObjectName("EditorHeader")
        self._editor = CodeEditor(read_only=True)
        self._editor.setMinimumWidth(320)
        code_layout.addWidget(self._file_label)
        code_layout.addWidget(self._editor, 1)
        splitter.addWidget(code_box)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 700])
        layout.addWidget(splitter, 1)
        return content

    # --- datos ----------------------------------------------------------------

    def clear(self) -> None:
        self._class = None
        self._stack.setCurrentIndex(0)

    def show_class(self, cls: JavaClass, role: ComponentRole) -> None:
        self._class = cls
        self._stack.setCurrentIndex(1)
        self._name.setText(display_name(cls))
        self._name.setToolTip(cls.qualified_name)
        self._location.setText(f"{cls.package or '(paquete por defecto)'} · líneas {cls.start_line}–{cls.end_line}")

        _clear_layout(self._chips)
        self._chips.addWidget(Chip(ROLE_LABELS[role][0], tone="accent", icon=f"role.{role.value}"))
        self._chips.addWidget(Chip(cls.kind.value))
        if cls.superclass:
            self._chips.addWidget(Chip(f"extends {cls.superclass}", tone="muted"))
        for interface in cls.interfaces[:2]:
            verb = "extends" if cls.kind is TypeKind.INTERFACE else "implements"
            self._chips.addWidget(Chip(f"{verb} {interface}", tone="muted"))
        self._chips.addStretch(1)

        _clear_layout(self._annotations)
        for annotation in cls.annotations[:_MAX_ANNOTATION_CHIPS]:
            chip = Chip(f"@{annotation.name}")
            chip.setToolTip(annotation.display)
            self._annotations.addWidget(chip)
        if len(cls.annotations) > _MAX_ANNOTATION_CHIPS:
            self._annotations.addWidget(muted(f"+{len(cls.annotations) - _MAX_ANNOTATION_CHIPS}", word_wrap=False))
        self._annotations.addStretch(1)
        self._annotations_holder.setVisible(bool(cls.annotations))

        self._fill_members(cls)
        self._show_code(cls)

    def _fill_members(self, cls: JavaClass) -> None:
        self._members.blockSignals(True)
        self._members.clear()
        if cls.enum_constants:
            self._add_group(f"CONSTANTES ({len(cls.enum_constants)})")
            for constant in cls.enum_constants:
                self._members.addTopLevelItem(QTreeWidgetItem([constant]))
        if cls.fields:
            self._add_group(f"CAMPOS ({len(cls.fields)})")
            for f in cls.fields:
                self._members.addTopLevelItem(self._field_item(f))
        if cls.methods:
            self._add_group(f"MÉTODOS ({len(cls.methods)})")
            for m in cls.methods:
                self._members.addTopLevelItem(self._method_item(m))
        self._members.blockSignals(False)

    def _add_group(self, title: str) -> None:
        item = QTreeWidgetItem([title])
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(0, QBrush(QColor(current_palette().text_subtle)))
        font = item.font(0)
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 0.85)
        item.setFont(0, font)
        self._members.addTopLevelItem(item)

    def _field_item(self, f: JavaField) -> QTreeWidgetItem:
        item = QTreeWidgetItem([f"{f.name}: {f.type}"])
        item.setIcon(0, icon("field", current_palette().syntax_number))
        item.setToolTip(0, "\n".join([*(a.display for a in f.annotations), " ".join([*f.modifiers, f.type, f.name])]))
        item.setData(0, _LINES_ROLE, (f.start_line, f.end_line))
        return item

    def _method_item(self, m: JavaMethod) -> QTreeWidgetItem:
        params = ", ".join(p.type for p in m.parameters)
        label = f"{m.name}({params})" + ("" if m.is_constructor else f": {m.return_type}")
        item = QTreeWidgetItem([label])
        item.setIcon(0, icon("method", current_palette().syntax_annotation))
        tooltip = [a.display for a in m.annotations]
        tooltip.append(" ".join([*m.modifiers, m.return_type or "", m.signature]).strip())
        item.setToolTip(0, "\n".join(tooltip))
        item.setData(0, _LINES_ROLE, (m.start_line, m.end_line))
        return item

    def _show_code(self, cls: JavaClass) -> None:
        self._file_label.setText(f"{PurePosixPath(cls.file).name}  ·  {cls.file}")
        try:
            snippet = self._load_source(cls)
        except (OSError, ValueError) as exc:
            log.warning("No se pudo leer %s: %s", cls.file, exc)
            self._editor.set_code(f"// No se pudo leer el archivo: {exc}")
            return
        self._editor.set_code(snippet.text, first_line=snippet.start_line)
        if cls.enclosing:  # clase anidada: resalta su bloque dentro del archivo
            self._editor.highlight_lines(range(cls.start_line, cls.end_line + 1))
        else:
            self._editor.scroll_to_line(cls.start_line)

    def _on_member_selected(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        lines = current.data(0, _LINES_ROLE) if current is not None else None
        if lines:
            start, end = lines
            self._editor.highlight_lines(range(start, end + 1))


def _clear_layout(layout: QHBoxLayout) -> None:
    while (item := layout.takeAt(0)) is not None:
        if widget := item.widget():
            widget.hide()
            widget.deleteLater()
