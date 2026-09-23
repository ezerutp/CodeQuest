import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from codequest.ui.dialogs import build_confirm  # noqa: E402
from codequest.ui.theme import DARK, apply_palette  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_confirm_uses_spanish_buttons_and_cancels_by_default(qapp: QApplication) -> None:
    box, accept = build_confirm(None, "Título", "¿Seguro?", confirm_text="Generar con IA")

    texts = sorted(b.text() for b in box.buttons())
    assert texts == ["Cancelar", "Generar con IA"]
    assert box.defaultButton() is not accept and box.escapeButton() is not accept


def test_application_palette_is_dark_for_secondary_windows(qapp: QApplication) -> None:
    apply_palette(qapp, DARK)
    palette = qapp.palette()

    window, text = palette.color(QPalette.ColorRole.Window), palette.color(QPalette.ColorRole.WindowText)
    assert window.name() == DARK.surface and text.name() == DARK.text
    assert window.lightness() < 60 < text.lightness()  # texto claro sobre fondo oscuro: legible
