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

GAME_MODES: tuple[ModeInfo, ...] = (
    ModeInfo(MULTIPLE_CHOICE, "Alternativas", "Responde preguntas sobre tu propio código.", available=True),
    ModeInfo("explain_code", "Explícame este código", "Describe con tus palabras qué hace un fragmento.",
             uses_ai=True),
    ModeInfo("find_error", "Encuentra el error", "Descubre el error escondido en código real."),
    ModeInfo("fix_code", "Corrige el código", "Edita el fragmento hasta que funcione."),
    ModeInfo("comparison", "Comparaciones", "@Controller vs @RestController, Entity vs DTO…"),
    ModeInfo("random", "Desafío aleatorio", "No sabes qué ejercicio aparecerá."),
)


def mode_info(mode_id: str) -> ModeInfo:
    return next(m for m in GAME_MODES if m.id == mode_id)
