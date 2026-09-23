"""Conocimiento general (independiente del proyecto del estudiante)."""

from dataclasses import dataclass, field
from enum import StrEnum


class Topic(StrEnum):
    """Tema de un concepto. El valor es el id estable que se escribe en los YAML."""

    WEB = "web"
    DI = "di"
    JPA = "jpa"
    DATA = "data"
    TRANSACTIONS = "transactions"
    VALIDATION = "validation"
    ERRORS = "errors"
    CONFIG = "config"
    OTHER = "other"

    @property
    def label(self) -> str:
        return _TOPIC_LABELS[self]


_TOPIC_LABELS = {
    Topic.WEB: "Spring Web",
    Topic.DI: "Inyección de dependencias",
    Topic.JPA: "JPA",
    Topic.DATA: "Spring Data",
    Topic.TRANSACTIONS: "Transacciones",
    Topic.VALIDATION: "Validación",
    Topic.ERRORS: "Manejo de errores",
    Topic.CONFIG: "Configuración",
    Topic.OTHER: "Otros",
}


class ConceptSource(StrEnum):
    """De dónde viene un concepto. Los integrados tienen prioridad sobre el resto."""

    BUILTIN = "builtin"  # incluido con CodeQuest y revisado a mano
    USER = "user"  # añadido por el usuario en su carpeta de conocimiento
    AI = "ai"  # generado con IA y guardado en la caché local (GCQ-05)


@dataclass(frozen=True, slots=True)
class ConceptMatch:
    """Qué elementos del código explica el concepto (nombres simples)."""

    annotations: tuple[str, ...] = ()  # "Transactional"
    supertypes: tuple[str, ...] = ()  # "JpaRepository"


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
    matches: ConceptMatch = field(default_factory=ConceptMatch)
    source: ConceptSource = ConceptSource.BUILTIN
