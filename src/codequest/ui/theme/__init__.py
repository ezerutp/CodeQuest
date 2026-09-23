from codequest.ui.theme.loader import load_stylesheet
from codequest.ui.theme.palette import DARK, Palette
from codequest.ui.theme.qt_palette import apply_palette


def current_palette() -> Palette:
    """Paleta activa. Cuando exista tema claro, se leerá de la configuración."""
    return DARK


__all__ = ["DARK", "Palette", "apply_palette", "current_palette", "load_stylesheet"]
