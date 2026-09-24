from dataclasses import dataclass

from codequest.core.analysis.snippets import SnippetRef
from codequest.core.knowledge.models import Concept


@dataclass(frozen=True, slots=True)
class CodeMutation:
    """Receta de un error en una sola línea. Se aplica sobre una copia en memoria; nunca toca el archivo.

    Las posiciones vienen del parser: línea real y columnas en caracteres del tramo que se sustituye.
    """

    line: int
    column: int
    end_column: int
    original: str  # con lo que debe empezar el tramo: "@GetMapping", "save"
    replacement: str  # texto que ocupa todo el tramo: "@PostMapping", "delete"
    explanation: str  # por qué es un error en este contexto

    def apply(self, text: str, first_line: int) -> str:
        """Devuelve el fragmento con el error. Lanza ValueError si el código cambió desde el análisis."""
        lines = text.split("\n")
        index = self.line - first_line
        if not 0 <= index < len(lines) or not lines[index][self.column:self.end_column].startswith(self.original):
            raise ValueError("el código cambió desde el análisis")
        line = lines[index]
        lines[index] = line[:self.column] + self.replacement + line[self.end_column:]
        return "\n".join(lines)


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
    mutation: CodeMutation | None = None  # solo en "Encuentra el error"


@dataclass(frozen=True, slots=True)
class Question:
    key: str
    prompt: str
    concept: Concept
    class_name: str
    snippet: SnippetRef | None
    choices: tuple[str, ...] = ()  # vacío en ejercicios de respuesta libre
    correct_index: int = -1
    mutation: CodeMutation | None = None  # solo en "Encuentra el error"

    @property
    def is_free_text(self) -> bool:
        return not self.choices

    @property
    def correct_choice(self) -> str:
        return self.choices[self.correct_index] if self.choices else self.concept.summary
