"""Paleta de Qt a partir de los tokens del tema.

El QSS solo cubre los widgets que selecciona; los diálogos (QMessageBox, QFileDialog) son
ventanas aparte que toman sus colores de la QPalette. Sin esto salen con fondo claro del
sistema y el texto claro del tema encima: ilegibles.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from codequest.ui.theme.palette import Palette

R = QPalette.ColorRole
G = QPalette.ColorGroup


def build_qpalette(p: Palette) -> QPalette:
    qp = QPalette()
    roles = {
        R.Window: p.surface,
        R.WindowText: p.text,
        R.Base: p.bg,
        R.AlternateBase: p.surface_raised,
        R.Text: p.text,
        R.Button: p.surface_raised,
        R.ButtonText: p.text,
        R.BrightText: "#ffffff",
        R.Highlight: p.accent,
        R.HighlightedText: "#ffffff",
        R.ToolTipBase: p.surface_raised,
        R.ToolTipText: p.text,
        R.PlaceholderText: p.text_subtle,
        R.Link: p.accent_hover,
        R.Mid: p.border,
        R.Dark: p.bg_sidebar,
        R.Light: p.border_strong,
    }
    for role, color in roles.items():
        qp.setColor(role, QColor(color))
    for role in (R.WindowText, R.Text, R.ButtonText):
        qp.setColor(G.Disabled, role, QColor(p.text_subtle))
    return qp


def apply_palette(app: QApplication, palette: Palette) -> None:
    app.setPalette(build_qpalette(palette))
