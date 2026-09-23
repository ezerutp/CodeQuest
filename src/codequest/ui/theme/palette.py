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
    # Editor de código
    editor_bg: str
    editor_gutter: str
    editor_line_number: str
    editor_line_number_active: str
    editor_current_line: str
    editor_highlight_line: str
    editor_selection: str
    syntax_keyword: str
    syntax_type: str
    syntax_string: str
    syntax_number: str
    syntax_comment: str
    syntax_annotation: str

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
    editor_bg="#0d1117",
    editor_gutter="#0d1117",
    editor_line_number="#484f58",
    editor_line_number_active="#e6edf3",
    editor_current_line="#161b22",
    editor_highlight_line="#2a2145",
    editor_selection="#264f78",
    syntax_keyword="#ff7b72",
    syntax_type="#ffa657",
    syntax_string="#a5d6ff",
    syntax_number="#79c0ff",
    syntax_comment="#8b949e",
    syntax_annotation="#d2a8ff",
)
