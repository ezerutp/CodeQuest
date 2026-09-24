"""Comparaciones entre conceptos parecidos (@RestController vs @Controller, Entity vs DTO…).

Cada comparación se ancla a un concepto que el proyecto usa (`concept`) y lo contrasta con una
alternativa (`versus`). Contenido integrado, en YAML (formato en docs/KNOWLEDGE.md), con las
mismas reglas de calidad que los conceptos.
"""

from dataclasses import dataclass, replace
from functools import cache
from importlib import resources
from typing import Any

import yaml

from codequest.core.knowledge.loader import SUPPORTED_VERSION, KnowledgeFormatError
from codequest.core.knowledge.models import Concept
from codequest.core.knowledge.validation import answer_problems

BUILTIN_PACKAGE = "codequest.resources.comparisons"
_SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_TEXT_FIELDS = ("id", "concept", "versus", "summary", "explanation", "analogy", "youtube_query")


@dataclass(frozen=True, slots=True)
class Comparison:
    id: str  # "compare.rest-controller-vs-controller"
    concept_id: str  # concepto que usa el proyecto: "spring.rest-controller"
    versus: str  # la alternativa, tal como se muestra: "@Controller"
    summary: str  # la diferencia clave: es la opción correcta
    explanation: str
    analogy: str
    distractors: tuple[str, ...]
    youtube_query: str

    def as_concept(self, anchor: Concept) -> Concept:
        """El concepto ancla con el contenido de la comparación.

        Las preguntas y el feedback trabajan con conceptos; conservar el id del ancla hace que
        acertar la comparación cuente para el dominio de ese concepto (entender la diferencia es
        parte de entenderlo) sin tocar el progreso ni el panel de feedback.
        """
        return replace(anchor, title=f"{anchor.title} vs {self.versus}", summary=self.summary,
                       explanation=self.explanation, analogy=self.analogy, distractors=self.distractors,
                       youtube_query=self.youtube_query)


def parse_comparisons(text: str, origin: str) -> list[Comparison]:
    try:
        data = yaml.load(text, Loader=_SafeLoader)  # noqa: S506 (es un SafeLoader)
    except yaml.YAMLError as exc:
        raise KnowledgeFormatError(f"{origin}: YAML no válido ({exc})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("comparisons"), list):
        raise KnowledgeFormatError(f"{origin}: se esperaba un mapa con la lista 'comparisons'")
    if data.get("version", SUPPORTED_VERSION) != SUPPORTED_VERSION:
        raise KnowledgeFormatError(f"{origin}: versión {data.get('version')} no soportada")
    return [_comparison(entry, f"{origin}#{index}") for index, entry in enumerate(data["comparisons"])]


@cache  # contenido inmutable del paquete: se lee una sola vez
def load_builtin_comparisons() -> tuple[Comparison, ...]:
    """Comparaciones incluidas con CodeQuest. Un error aquí es un bug nuestro: se lanza."""
    found: list[Comparison] = []
    for file in sorted(resources.files(BUILTIN_PACKAGE).iterdir(), key=lambda f: f.name):
        if file.name.endswith((".yaml", ".yml")):
            found.extend(parse_comparisons(file.read_text(encoding="utf-8"), file.name))
    ids = [c.id for c in found]
    if len(ids) != len(set(ids)):
        raise KnowledgeFormatError("hay comparaciones con el mismo id")
    return tuple(found)


def _comparison(entry: Any, where: str) -> Comparison:
    if not isinstance(entry, dict):
        raise KnowledgeFormatError(f"{where}: cada comparación debe ser un mapa")
    where = f"{where} ({entry.get('id', '?')})"
    missing = [name for name in _TEXT_FIELDS if not isinstance(entry.get(name), str) or not entry[name].strip()]
    distractors = entry.get("distractors")
    if missing:
        raise KnowledgeFormatError(f"{where}: faltan los campos {', '.join(missing)}")
    if not isinstance(distractors, list) or not all(isinstance(d, str) for d in distractors):
        raise KnowledgeFormatError(f"{where}: 'distractors' debe ser una lista de textos")
    comparison = Comparison(
        id=entry["id"].strip(), concept_id=entry["concept"].strip(), versus=entry["versus"].strip(),
        summary=entry["summary"].strip(), explanation=entry["explanation"].strip(),
        analogy=entry["analogy"].strip(), distractors=tuple(d.strip() for d in distractors),
        youtube_query=entry["youtube_query"].strip(),
    )
    if problems := answer_problems(comparison.summary, comparison.distractors):
        raise KnowledgeFormatError(f"{where}: " + "; ".join(problems))
    return comparison
