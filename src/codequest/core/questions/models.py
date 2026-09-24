from dataclasses import dataclass

from codequest.core.analysis.snippets import SnippetRef
from codequest.core.knowledge.models import Concept


@dataclass(frozen=True, slots=True)
class QuestionDraft:
    """Pregunta sin alternativas: lo que produce una regla a partir del código."""

    key: str  # estable entre sesiones: identifica la pregunta en el historial
    prompt: str
    concept: Concept
    class_name: str  # nombre cualificado de la clase de origen
    snippet: SnippetRef | None
    # Sujeto para afirmaciones de Verdadero/Falso: "En tu método `x()` de `C`, `@Transactional`".
    statement_lead: str = ""


@dataclass(frozen=True, slots=True)
class Question:
    key: str
    prompt: str
    concept: Concept
    class_name: str
    snippet: SnippetRef | None
    choices: tuple[str, ...] = ()  # vacío en ejercicios de respuesta libre
    correct_index: int = -1

    @property
    def is_free_text(self) -> bool:
        return not self.choices

    @property
    def correct_choice(self) -> str:
        return self.choices[self.correct_index] if self.choices else self.concept.summary
