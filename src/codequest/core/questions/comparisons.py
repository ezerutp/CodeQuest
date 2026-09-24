"""Preguntas de "Comparaciones": la diferencia entre lo que usa tu código y su alternativa.

Solo se pregunta por comparaciones cuyo concepto ancla aparece en el proyecto, y el fragmento
es el sitio real donde se usa: "En `UserController` usas `@RestController`. ¿Qué lo diferencia
de `@Controller`?".
"""

from collections.abc import Iterable, Iterator

from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.package_tree import display_name
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.comparisons import Comparison, load_builtin_comparisons
from codequest.core.questions.models import QuestionDraft
from codequest.core.questions.rules import DEFAULT_RULES, QuestionRule


class ComparisonRule(QuestionRule):
    """Reutiliza las reglas de Alternativas para encontrar dónde se usa cada concepto ancla."""

    def __init__(self, comparisons: Iterable[Comparison] | None = None,
                 sources: tuple[QuestionRule, ...] = DEFAULT_RULES) -> None:
        self._comparisons = tuple(load_builtin_comparisons() if comparisons is None else comparisons)
        self._sources = sources

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        by_concept: dict[str, list[Comparison]] = {}
        for comparison in self._comparisons:
            by_concept.setdefault(comparison.concept_id, []).append(comparison)
        classes = {c.qualified_name: c for c in model.classes}
        seen: set[str] = set()
        for rule in self._sources:
            for draft in rule.drafts(model, kb):
                for comparison in by_concept.get(draft.concept.id, ()):
                    key = f"compare:{comparison.id}:{draft.class_name}"
                    if key in seen:  # una pregunta por comparación y clase, en su primer uso
                        continue
                    seen.add(key)
                    cls = classes.get(draft.class_name)
                    name = display_name(cls) if cls else draft.class_name
                    yield QuestionDraft(
                        key=key,
                        prompt=f"En `{name}` usas `{draft.concept.title}`. "
                               f"¿Qué lo diferencia de {_as_code(comparison.versus)}?",
                        concept=comparison.as_concept(draft.concept),
                        class_name=draft.class_name,
                        snippet=draft.snippet,
                    )


def _as_code(text: str) -> str:
    """`@Controller`, `CrudRepository` o "`@ExceptionHandler` dentro de…" van como código; "un DTO", no."""
    first, _, rest = text.partition(" ")
    if not rest or first.startswith("@"):
        return f"`{first}` {rest}".rstrip()
    return text


COMPARISON_RULES: tuple[QuestionRule, ...] = (ComparisonRule(),)
