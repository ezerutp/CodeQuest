"""Lectura de conceptos desde YAML: los integrados (paquete) y los de la carpeta del usuario.

Formato documentado en docs/KNOWLEDGE.md. Solo lectura: escribir en la caché es cosa de GCQ-05.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from codequest.core.knowledge.models import Concept, ConceptMatch, ConceptSource, Topic
from codequest.core.knowledge.validation import concept_problems

log = logging.getLogger(__name__)

# El parser en C (libyaml) es ~10 veces más rápido; si no está disponible, el de Python puro.
_SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

SUPPORTED_VERSION = 1
BUILTIN_PACKAGE = "codequest.resources.knowledge"


class KnowledgeFormatError(ValueError):
    """Un archivo de conocimiento no respeta el formato o las reglas de calidad."""


@dataclass(frozen=True, slots=True)
class LoadIssue:
    """Problema no fatal al cargar la carpeta del usuario: se muestra en la UI."""

    location: str  # archivo (y concepto, si aplica)
    message: str


USER_SOURCES = frozenset({ConceptSource.USER, ConceptSource.AI})


def parse_concepts(text: str, source: ConceptSource, origin: str,
                   allowed_sources: frozenset[ConceptSource] | None = None) -> list[Concept]:
    """Convierte el contenido de un archivo YAML en conceptos validados.

    Si `allowed_sources` se indica, el archivo puede declarar su propio `source` (p. ej. "ai"),
    pero solo uno de esos: un archivo del usuario nunca puede hacerse pasar por integrado.
    """
    try:
        data = yaml.load(text, Loader=_SafeLoader)  # noqa: S506 (es un SafeLoader)
    except yaml.YAMLError as exc:
        raise KnowledgeFormatError(f"{origin}: {_describe_yaml_error(exc)}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("concepts"), list):
        raise KnowledgeFormatError(f"{origin}: se esperaba un mapa con la lista 'concepts'")
    if data.get("version", SUPPORTED_VERSION) != SUPPORTED_VERSION:
        raise KnowledgeFormatError(f"{origin}: versión {data.get('version')} no soportada")
    if "source" in data:
        try:
            declared = ConceptSource(data["source"])
        except ValueError as exc:
            raise KnowledgeFormatError(f"{origin}: source desconocido '{data['source']}'") from exc
        if allowed_sources is None or declared not in allowed_sources:
            raise KnowledgeFormatError(f"{origin}: este archivo no puede declarar source '{declared}'")
        source = declared
    return [_concept(entry, source, f"{origin}#{index}") for index, entry in enumerate(data["concepts"])]


@cache  # contenido inmutable del paquete: se lee una sola vez
def load_builtin() -> tuple[Concept, ...]:
    """Conceptos incluidos con CodeQuest. Un error aquí es un bug nuestro: se lanza."""
    concepts: list[Concept] = []
    for file in sorted(resources.files(BUILTIN_PACKAGE).iterdir(), key=lambda f: f.name):
        if file.name.endswith((".yaml", ".yml")):
            concepts.extend(parse_concepts(file.read_text(encoding="utf-8"), ConceptSource.BUILTIN, file.name))
    return tuple(concepts)


def load_directory(directory: Path, source: ConceptSource = ConceptSource.USER,
                   ) -> tuple[list[Concept], list[LoadIssue]]:
    """Conceptos de una carpeta del usuario. Los archivos inválidos se omiten y se informan."""
    concepts: list[Concept] = []
    issues: list[LoadIssue] = []
    if not directory.is_dir():
        return concepts, issues
    for path in sorted(_yaml_files(directory)):
        try:
            text = path.read_text(encoding="utf-8")
            concepts.extend(parse_concepts(text, source, path.name, allowed_sources=USER_SOURCES))
        except (OSError, KnowledgeFormatError) as exc:
            log.warning("Conocimiento omitido %s: %s", path, exc)
            issues.append(LoadIssue(path.name, str(exc).removeprefix(f"{path.name}: ")))
    return concepts, issues


def _describe_yaml_error(exc: yaml.YAMLError) -> str:
    """Mensaje de una línea: "YAML inválido en la línea 2: did not find expected node content"."""
    mark = getattr(exc, "problem_mark", None)
    problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
    where = f" en la línea {mark.line + 1}" if mark is not None else ""
    return f"YAML inválido{where}: {problem}"


def _yaml_files(directory: Path) -> Iterator[Path]:
    for pattern in ("*.yaml", "*.yml"):
        yield from directory.glob(pattern)


def _concept(entry: Any, source: ConceptSource, origin: str) -> Concept:
    if not isinstance(entry, dict):
        raise KnowledgeFormatError(f"{origin}: cada concepto debe ser un mapa")
    where = f"{origin} ({entry.get('id', '?')})"
    try:
        topic = Topic(entry.get("topic", Topic.OTHER.value))
    except ValueError as exc:
        raise KnowledgeFormatError(f"{where}: tema desconocido '{entry.get('topic')}'") from exc
    matches = entry.get("matches") or {}
    concept = Concept(
        id=_text(entry, "id", where),
        title=_text(entry, "title", where),
        topic=topic,
        summary=_text(entry, "summary", where),
        explanation=_text(entry, "explanation", where).strip(),
        analogy=_text(entry, "analogy", where),
        distractors=_texts(entry.get("distractors"), "distractors", where),
        youtube_query=_text(entry, "youtube_query", where),
        matches=ConceptMatch(
            annotations=_texts(matches.get("annotations"), "matches.annotations", where, allow_empty=True),
            supertypes=_texts(matches.get("supertypes"), "matches.supertypes", where, allow_empty=True),
        ),
        source=source,
    )
    if problems := concept_problems(concept):
        raise KnowledgeFormatError(f"{where}: " + "; ".join(problems))
    return concept


def _text(entry: dict, key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeFormatError(f"{where}: el campo '{key}' debe ser un texto no vacío")
    return value.strip() if key != "explanation" else value


def _texts(value: Any, key: str, where: str, allow_empty: bool = False) -> tuple[str, ...]:
    if value is None and allow_empty:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise KnowledgeFormatError(f"{where}: '{key}' debe ser una lista de textos")
    return tuple(v.strip() for v in value if v.strip())
