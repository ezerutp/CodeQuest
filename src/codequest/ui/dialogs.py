"""Diálogos con el estilo de CodeQuest: textos en español e iconos propios.

Usar siempre estas funciones en lugar de QMessageBox.question/warning directamente.
"""

from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from codequest.app.constants import APP_NAME
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
