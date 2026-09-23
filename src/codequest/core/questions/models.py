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


@dataclass(frozen=True, slots=True)
class Question:
    key: str
    prompt: str
    concept: Concept
    class_name: str
    snippet: SnippetRef | None
    choices: tuple[str, ...]
    correct_index: int

    @property
    def correct_choice(self) -> str:
        return self.choices[self.correct_index]
