"""Árbol de paquetes y clases con búsqueda y filtro por tipo."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QComboBox, QLineEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from codequest.core.analysis.java.models import JavaClass
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.package_tree import PackageNode, build_package_tree, display_name
from codequest.core.analysis.roles import ComponentRole
from codequest.ui.formatting import ROLE_LABELS, role_color
from codequest.ui.icons import icon

_CLASS_ROLE = Qt.ItemDataRole.UserRole
_EXPAND_ALL_LIMIT = 150  # con más clases solo se expande el primer nivel


class ClassTree(QWidget):
    class_selected = Signal(object)  # JavaClass

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model: ProjectModel | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar clase…")
        self._search.addAction(icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._rebuild)
        layout.addWidget(self._search)

        self._role_filter = QComboBox()
        self._role_filter.currentIndexChanged.connect(self._rebuild)
        layout.addWidget(self._role_filter)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIconSize(QSize(16, 16))
        self._tree.setIndentation(14)
        self._tree.setUniformRowHeights(True)
        self._tree.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self._tree, 1)

    def set_model(self, model: ProjectModel | None) -> None:
        self._model = model
        self._role_filter.blockSignals(True)
        self._role_filter.clear()
        self._role_filter.addItem("Todos los tipos", None)
        if model is not None:
            counts = model.role_counts()
            for role in ComponentRole:
                if counts[role]:
                    self._role_filter.addItem(icon(f"role.{role.value}", role_color(role)),
                                              f"{ROLE_LABELS[role][1]} ({counts[role]})", role)
        self._role_filter.blockSignals(False)
        self._search.clear()
        self._rebuild()

    def select_class(self, qualified_name: str) -> None:
        for item in self._iter_items():
            cls = item.data(0, _CLASS_ROLE)
            if cls is not None and cls.qualified_name == qualified_name:
                self._tree.setCurrentItem(item)
                return

    # --- construcción -------------------------------------------------------

    def _rebuild(self) -> None:
        self._tree.clear()
        if self._model is None:
            return
        query = self._search.text().strip().lower()
        role = self._role_filter.currentData()
        classes = [
            c for c in self._model.main_classes
            if (not query or query in display_name(c).lower())
            and (role is None or self._model.role_of(c) is role)
        ]
        root = build_package_tree(classes)
        for package in root.packages:
            self._tree.addTopLevelItem(self._package_item(package))
        for cls in root.classes:
            self._tree.addTopLevelItem(self._class_item(cls))

        if query or role is not None or len(classes) <= _EXPAND_ALL_LIMIT:
            self._tree.expandAll()
        else:
            for i in range(self._tree.topLevelItemCount()):
                self._tree.topLevelItem(i).setExpanded(True)

    def _package_item(self, node: PackageNode) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.name])
        item.setIcon(0, icon("package"))
        item.setToolTip(0, f"{node.full_name} · {node.class_count()} clases")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        for child in node.packages:
            item.addChild(self._package_item(child))
        for cls in node.classes:
            item.addChild(self._class_item(cls))
        return item

    def _class_item(self, cls: JavaClass) -> QTreeWidgetItem:
        assert self._model is not None
        role = self._model.role_of(cls)
        item = QTreeWidgetItem([display_name(cls)])
        item.setIcon(0, icon(f"role.{role.value}", role_color(role)))
        item.setToolTip(0, f"{ROLE_LABELS[role][0]} · {cls.file}")
        item.setData(0, _CLASS_ROLE, cls)
        return item

    def _iter_items(self):
        stack = [self._tree.topLevelItem(i) for i in range(self._tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            yield item
            stack.extend(item.child(i) for i in range(item.childCount()))

    def _on_current_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        cls = current.data(0, _CLASS_ROLE) if current is not None else None
        if cls is not None:
            self.class_selected.emit(cls)
