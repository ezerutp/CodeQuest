from codequest.ui.theme.loader import load_stylesheet
from codequest.ui.theme.palette import DARK, Palette


def current_palette() -> Palette:
    """Paleta activa. Cuando exista tema claro, se leerá de la configuración."""
    return DARK


__all__ = ["DARK", "Palette", "current_palette", "load_stylesheet"]
