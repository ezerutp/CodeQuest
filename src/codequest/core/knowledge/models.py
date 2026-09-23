"""Conocimiento general (independiente del proyecto del estudiante)."""

from dataclasses import dataclass
from enum import StrEnum


class Topic(StrEnum):
    WEB = "Spring Web"
    DI = "Inyección de dependencias"
    JPA = "JPA"
    DATA = "Spring Data"
    TRANSACTIONS = "Transacciones"
    VALIDATION = "Validación"
    ERRORS = "Manejo de errores"
    CONFIG = "Configuración"


@dataclass(frozen=True, slots=True)
class Concept:
    id: str  # estable: "spring.transactional"
    title: str  # "@Transactional"
    topic: Topic
    summary: str  # una frase: es la opción correcta en las preguntas de alternativas
    explanation: str  # párrafos separados por línea en blanco
    analogy: str
    distractors: tuple[str, ...]  # afirmaciones falsas pero plausibles, mismo estilo que `summary`
    youtube_query: str
