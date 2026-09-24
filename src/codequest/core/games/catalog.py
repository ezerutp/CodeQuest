"""Catálogo de modos de juego: la UI lo muestra y los servicios lo usan para crear partidas."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModeInfo:
    id: str
    title: str
    description: str
    uses_ai: bool = False
    available: bool = False


MULTIPLE_CHOICE = "multiple_choice"
EXPLAIN_CODE = "explain_code"
TRUE_FALSE = "true_false"
FIND_ERROR = "find_error"
FIX_CODE = "fix_code"

GAME_MODES: tuple[ModeInfo, ...] = (
    ModeInfo(MULTIPLE_CHOICE, "Alternativas", "Responde preguntas sobre tu propio código.", available=True),
    ModeInfo(TRUE_FALSE, "Verdadero o falso", "Decide si la afirmación sobre tu código es cierta.", available=True),
    ModeInfo(EXPLAIN_CODE, "Explícame este código", "Describe con tus palabras qué hace un fragmento.",
             uses_ai=True, available=True),
    ModeInfo(FIND_ERROR, "Encuentra el error", "Descubre la línea que alguien cambió en tu código.",
             available=True),
    ModeInfo(FIX_CODE, "Corrige el código", "Edita tu código hasta dejarlo sin el error.", available=True),
    ModeInfo("comparison", "Comparaciones", "@Controller vs @RestController, Entity vs DTO…"),
    ModeInfo("random", "Desafío aleatorio", "No sabes qué ejercicio aparecerá."),
)


def mode_info(mode_id: str) -> ModeInfo:
    return next(m for m in GAME_MODES if m.id == mode_id)


def mode_title(mode_id: str) -> str:
    """Título legible de un modo guardado en el historial (tolerante a modos antiguos)."""
    return next((m.title for m in GAME_MODES if m.id == mode_id), mode_id)
