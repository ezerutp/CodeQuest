"""Tokens de color del tema. Los QSS los referencian como ${nombre}."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Palette:
    bg: str
    bg_sidebar: str
    surface: str
    surface_hover: str
    surface_raised: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_subtle: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    success: str
    warning: str
    warning_soft: str
    danger: str

    def tokens(self) -> dict[str, str]:
        return asdict(self)


DARK = Palette(
    bg="#0d1117",
    bg_sidebar="#010409",
    surface="#161b22",
    surface_hover="#1c2230",
    surface_raised="#21262d",
    border="#30363d",
    border_strong="#484f58",
    text="#f0f6fc",
    text_muted="#8b949e",
    text_subtle="#6e7681",
    accent="#7c5cff",
    accent_hover="#8f73ff",
    accent_pressed="#6a4ae6",
    accent_soft="#241d45",
    success="#3fb950",
    warning="#d29922",
    warning_soft="#2b2111",
    danger="#f85149",
)
