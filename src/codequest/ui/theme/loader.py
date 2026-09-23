"""Carga y combina los archivos QSS modulares aplicando la paleta."""

import logging
from importlib import resources
from string import Template

from codequest.ui.theme.palette import Palette

log = logging.getLogger(__name__)

# El orden importa: las reglas posteriores pueden refinar a las anteriores.
STYLE_FILES: tuple[str, ...] = (
    "base.qss", "sidebar.qss", "cards.qss", "buttons.qss", "badges.qss", "inputs.qss", "lists.qss", "editor.qss",
    "game.qss",
)


def load_stylesheet(palette: Palette) -> str:
    styles = resources.files("codequest.ui.styles")
    tokens = palette.tokens()
    chunks: list[str] = []
    for name in STYLE_FILES:
        try:
            raw = styles.joinpath(name).read_text(encoding="utf-8")
        except FileNotFoundError:
            log.error("Hoja de estilos no encontrada: %s", name)
            continue
        # substitute() falla si falta un token: preferimos descubrirlo pronto.
        chunks.append(f"/* {name} */\n" + Template(raw).substitute(tokens))
    return "\n".join(chunks)
