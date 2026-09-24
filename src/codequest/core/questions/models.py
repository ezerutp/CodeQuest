import re
from dataclasses import dataclass

from codequest.core.analysis.snippets import SnippetRef
from codequest.core.knowledge.models import Concept


@dataclass(frozen=True, slots=True)
class CodeMutation:
    """Receta de un error introducido en una copia en memoria del fragmento. Nunca toca el archivo."""

    line: int  # numeración real del archivo
    find: str  # texto que se sustituye en esa línea (p. ej. "@GetMapping")
    replace: str  # texto que lo sustituye (p. ej. "@PostMapping")
    explanation: str  # por qué es un error en este contexto
    # Quitar también "(…)": `@RequestBody("id")` o `@ManyToOne(mappedBy = …)` delatarían el cambio.
    drop_arguments: bool = False

    def apply(self, text: str, first_line: int) -> str:
        """Devuelve el fragmento con el error. Lanza ValueError si la línea ya no contiene `find`."""
        lines = text.split("\n")
        index = self.line - first_line
        arguments = r"(\s*\([^()]*\))?" if self.drop_arguments else ""
        pattern = re.compile(rf"{re.escape(self.find)}\b{arguments}")  # "@Id" no debe tocar "@IdClass"
        if not 0 <= index < len(lines) or not pattern.search(lines[index]):
            raise ValueError("el código cambió desde el análisis")
        lines[index] = pattern.sub(self.replace, lines[index], count=1)
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
