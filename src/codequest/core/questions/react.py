"""Reglas de preguntas para proyectos React (TypeScript/TSX).

Donde en Java el concepto sale de una anotación (`@GetMapping`), en React sale de una llamada:
`useState(…)`, `useQuery(…)`. Cada llamada conocida por la KnowledgeBase (`matches.calls`) da
preguntas de Alternativas, Verdadero o falso y Comparaciones; los hooks con una sustitución creíble
dan además "Encuentra el error" y "Corrige el código".
"""

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass

from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.package_tree import display_name
from codequest.core.analysis.react.roles import ReactRole
from codequest.core.analysis.snippets import SnippetRef
from codequest.core.analysis.typescript.models import TSCall, TSClass, TSMethod
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.models import Concept
from codequest.core.questions.models import CodeMutation, QuestionDraft
from codequest.core.questions.mutations import PROMPT, FixCodeRule
from codequest.core.questions.rules import MAX_METHOD_LINES, QuestionRule

_DIRECT_RECEIVERS = (None, "React")  # useState(…) o React.useState(…)


@dataclass(frozen=True, slots=True)
class HookSwap:
    target: str  # hook que sustituye al original
    explanation: str  # plantilla con {where} ("el componente `Counter`") y {hook}


# Hook original -> sustitución que rompe el código de forma creíble (misma línea, solo el nombre).
HOOK_SWAPS: dict[str, HookSwap] = {
    "useState": HookSwap(
        "useRef",
        "En {where}, ese valor se muestra en pantalla y debe provocar un nuevo renderizado al cambiar. "
        "`useRef` no vuelve a dibujar el componente y además no devuelve el par `[valor, setter]`."),
    "useEffect": HookSwap(
        "useMemo",
        "En {where}, ese código es un efecto secundario que debe ejecutarse después de dibujar. Con "
        "`useMemo` se ejecutaría durante el renderizado y su función de limpieza nunca se llamaría."),
    "useMemo": HookSwap(
        "useEffect",
        "En {where}, hace falta el valor calculado. `useEffect` no devuelve nada: la variable quedaría "
        "`undefined` y el cálculo se haría después de dibujar, demasiado tarde."),
    "useCallback": HookSwap(
        "useMemo",
        "En {where}, `useCallback` guarda la función. `useMemo` la ejecutaría y guardaría lo que devuelve, "
        "así que la variable dejaría de ser una función."),
    "useContext": HookSwap(
        "useState",
        "En {where}, el valor lo comparte un Provider superior. Con `useState` se crearía un estado local "
        "con el contexto como valor inicial, y nunca vería los cambios del Provider."),
    "useQuery": HookSwap(
        "useMutation",
        "En {where}, los datos deben pedirse al dibujar. `useMutation` no pide nada hasta que alguien llama "
        "a `mutate`, y no devuelve `data` con la respuesta: la pantalla se quedaría vacía."),
    "useMutation": HookSwap(
        "useQuery",
        "En {where}, la operación debe esperar a que se llame a `mutate`. Con `useQuery` se lanzaría sola "
        "al dibujar el componente, y `mutate` dejaría de existir."),
    "useParams": HookSwap(
        "useSearchParams",
        "En {where}, el dato va en el camino de la URL (`/servicios/42`). `useSearchParams` lee lo que va "
        "después de `?`, así que el valor no aparecería."),
    "useSearchParams": HookSwap(
        "useParams",
        "En {where}, el dato va después de `?` en la URL (`?pagina=2`). `useParams` solo lee los parámetros "
        "del camino (`/:id`), así que el filtro se perdería."),
}


class HookPurposeRule(QuestionRule):
    """"¿Qué hace `useState` en el componente `Counter`?" para cada hook conocido."""

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        for cls, method, call, concept in _known_calls(model, kb):
            where = _where(model, cls, method)
            yield QuestionDraft(
                key=f"{concept.id}:{cls.qualified_name}" + _member(cls, method),
                prompt=f"¿Qué hace `{call.name}` en {where}?",
                concept=concept, class_name=cls.qualified_name,
                snippet=_window(cls, method, call.name_span.line),
                statement_lead=f"En {where}, `{call.name}`",
            )


class ExplainFunctionRule(QuestionRule):
    """"Explica con tus palabras qué hace este componente": funciones de tamaño razonable con un hook conocido."""

    MIN_LINES = 3
    MAX_LINES = 40

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        seen: set[str] = set()
        for cls, method, _call, concept in _known_calls(model, kb):
            key = f"explain:{cls.qualified_name}" + _member(cls, method)
            lines = method.end_line - method.start_line + 1
            if key in seen or not method.has_body or not self.MIN_LINES <= lines <= self.MAX_LINES:
                continue
            seen.add(key)
            yield QuestionDraft(
                key=key,
                prompt=f"Explica con tus propias palabras qué hace {_where(model, cls, method)}.",
                concept=concept, class_name=cls.qualified_name,
                snippet=SnippetRef(cls.file, method.start_line, method.end_line),
            )


class HookErrorRule(QuestionRule):
    """"Encuentra el error": un hook cambiado por otro que rompe ese código."""

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        seen: Counter[str] = Counter()
        for cls, method, call, concept in _known_calls(model, kb):
            swap = HOOK_SWAPS.get(call.name)
            span = call.name_span
            if swap is None or not span.is_single_line or span.end_column - span.column != len(call.name):
                continue
            base = f"error:{concept.id}:{cls.qualified_name}{_member(cls, method)}:{call.name}"
            seen[base] += 1
            yield QuestionDraft(
                key=base if seen[base] == 1 else f"{base}:{seen[base]}",
                prompt=PROMPT, concept=concept, class_name=cls.qualified_name,
                snippet=_window(cls, method, span.line, focus=False),  # resaltarla delataría el error
                mutation=CodeMutation(
                    line=span.line, column=span.column, end_column=span.end_column, original=call.name,
                    replacement=swap.target,
                    explanation=swap.explanation.format(where=_where(model, cls, method), hook=call.name),
                ),
            )


def _known_calls(model: ProjectModel, kb: KnowledgeBase) -> Iterator[tuple[TSClass, TSMethod, TSCall, Concept]]:
    """Llamadas directas a funciones que la KnowledgeBase explica, una vez por función y concepto
    (salvo en "Encuentra el error", que cuenta cada aparición por separado)."""
    for cls in model.main_classes:
        if not isinstance(cls, TSClass):
            continue
        for method in cls.methods:
            for call in method.calls:
                if call.receiver in _DIRECT_RECEIVERS and (concept := kb.for_call(call.name)) is not None:
                    yield cls, method, call, concept


def _where(model: ProjectModel, cls: TSClass, method: TSMethod) -> str:
    name = display_name(cls)
    if method.name != cls.name:  # método de una clase
        return f"el método `{method.name}()` de `{name}`"
    match model.role_of(cls):
        case ReactRole.COMPONENT:
            return f"el componente `{name}`"
        case ReactRole.HOOK:
            return f"el hook `{name}`"
        case _:
            return f"la función `{name}`"


def _member(cls: TSClass, method: TSMethod) -> str:
    return "" if method.name == cls.name else f"#{method.name}"


def _window(cls: TSClass, method: TSMethod, line: int, focus: bool = True) -> SnippetRef:
    """La función desde su inicio; si es larga, una ventana que incluya la línea de la llamada."""
    start = method.start_line
    if line > start + MAX_METHOD_LINES:
        start = line - MAX_METHOD_LINES // 2
    return SnippetRef(cls.file, start, min(method.end_line, start + MAX_METHOD_LINES), (line,) if focus else ())


REACT_RULES: tuple[QuestionRule, ...] = (HookPurposeRule(),)
REACT_EXPLAIN_RULES: tuple[QuestionRule, ...] = (ExplainFunctionRule(),)
REACT_FIND_ERROR_RULES: tuple[QuestionRule, ...] = (HookErrorRule(),)
REACT_FIX_CODE_RULES: tuple[QuestionRule, ...] = (FixCodeRule(HookErrorRule()),)
