"""Diálogos con el estilo de CodeQuest: textos en español e iconos propios.

Usar siempre estas funciones en lugar de QMessageBox.question/warning directamente.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from codequest.app.constants import APP_NAME
from codequest.core.project.models import ProjectInfo
from codequest.ui.icons import icon
from codequest.ui.theme import current_palette

_ICON_SIZE = 40


def _box(parent: QWidget | None, title: str, text: str, details: str | None, icon_name: str,
         color: str) -> QMessageBox:
    box = QMessageBox(parent)
    box.setWindowTitle(title or APP_NAME)
    box.setText(text)
    if details:
        box.setInformativeText(details)
    box.setIconPixmap(icon(icon_name, color).pixmap(_ICON_SIZE, _ICON_SIZE))
    return box


def build_confirm(parent: QWidget | None, title: str, text: str, details: str | None = None,
                  confirm_text: str = "Continuar", cancel_text: str = "Cancelar",
                  icon_name: str = "dont-know") -> tuple[QMessageBox, QPushButton]:
    """Crea el diálogo de confirmación sin mostrarlo. Devuelve (diálogo, botón de aceptar)."""
    box = _box(parent, title, text, details, icon_name, current_palette().syntax_annotation)
    # Con el diálogo como padre: addButton() no transfiere la propiedad en PySide y un botón
    # sin más referencias en Python se destruye al salir de la función.
    accept = QPushButton(confirm_text, box)
    accept.setProperty("variant", "primary")
    cancel = QPushButton(cancel_text, box)
    box.addButton(accept, QMessageBox.ButtonRole.AcceptRole)
    box.addButton(cancel, QMessageBox.ButtonRole.RejectRole)
    # Enter y Esc cancelan: nada se envía ni se borra por accidente.
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    return box, accept


def confirm(parent: QWidget | None, title: str, text: str, details: str | None = None,
            confirm_text: str = "Continuar", cancel_text: str = "Cancelar", icon_name: str = "dont-know") -> bool:
    box, accept = build_confirm(parent, title, text, details, confirm_text, cancel_text, icon_name)
    box.exec()
    return box.clickedButton() is accept


def warn(parent: QWidget | None, text: str, details: str | None = None, title: str = "") -> None:
    box = _box(parent, title, text, details, "warning", current_palette().warning)
    ok = QPushButton("Entendido", box)
    ok.setProperty("variant", "primary")
    box.addButton(ok, QMessageBox.ButtonRole.AcceptRole)
    box.exec()


class ProjectPickerDialog(QDialog):
    """Diálogo para elegir qué proyecto analizar cuando hay varios detectados."""

    def __init__(self, parent: QWidget | None, projects: list[ProjectInfo]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Elige un proyecto")
        self.setMinimumSize(480, 300)
        self._projects = projects
        self._selected: ProjectInfo | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Se encontraron varios proyectos", self)
        title.setProperty("variant", "heading")
        layout.addWidget(title)

        subtitle = QLabel("Elige cuál quieres estudiar:", self)
        subtitle.setProperty("variant", "muted")
        layout.addWidget(subtitle)

        self._list = QListWidget(self)
        self._list.setSpacing(4)
        for project in projects:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, project)
            item.setText(f"{project.name}  ·  {' · '.join(project.stack) or 'tipo desconocido'}")
            item.setIcon(icon("folder", current_palette().text))
            self._list.addItem(item)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self._list, 1)

        buttons = QDialogButtonBox(self)
        buttons.setOrientation(Qt.Orientation.Horizontal)
        self._accept_btn = QPushButton("Seleccionar", self)
        self._accept_btn.setProperty("variant", "primary")
        self._accept_btn.setEnabled(False)
        cancel_btn = QPushButton("Cancelar", self)
        buttons.addButton(self._accept_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if projects:
            self._list.setCurrentRow(0)

    def _on_selection_changed(self, current: QListWidgetItem, _previous: QListWidgetItem) -> None:
        self._selected = current.data(Qt.ItemDataRole.UserRole) if current else None
        self._accept_btn.setEnabled(current is not None)

    def _on_double_clicked(self, _item: QListWidgetItem) -> None:
        self.accept()

    @property
    def selected(self) -> ProjectInfo | None:
        return self._selected


def pick_project(parent: QWidget | None, projects: list[ProjectInfo]) -> ProjectInfo | None:
    """Muestra el diálogo de selección. Devuelve el proyecto elegido o None si se cancela.
    Si solo hay un proyecto, lo devuelve sin mostrar diálogo."""
    if len(projects) <= 1:
        return projects[0] if projects else None
    dialog = ProjectPickerDialog(parent, projects)
    dialog.exec()
    return dialog.selected if dialog.result() == QDialog.DialogCode.Accepted else None
