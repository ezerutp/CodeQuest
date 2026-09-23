"""Cobertura del conocimiento sobre un proyecto: qué conceptos usa y qué no conocemos aún."""

from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from codequest.core.analysis.java.conventions import simple_type_name
from codequest.core.analysis.java.models import JavaClass, TypeKind
from codequest.core.analysis.model import ProjectModel
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.models import Concept

# Anotaciones del propio lenguaje que no aportan un concepto de framework.
IGNORED_ANNOTATIONS = frozenset({
    "Override", "SuppressWarnings", "Deprecated", "SafeVarargs", "FunctionalInterface",
    # meta-anotaciones de java.lang.annotation (definen anotaciones propias)
    "Retention", "Target", "Documented", "Inherited", "Repeatable",
})

# Supertipos básicos de Java: no son un concepto de framework que haya que aprender aquí.
JAVA_BASIC_TYPES = frozenset({
    "Object", "Serializable", "Cloneable", "Comparable", "Comparator", "Iterable", "Runnable",
    "AutoCloseable", "Closeable", "Exception", "RuntimeException", "Error", "Throwable",
    "IllegalArgumentException", "IllegalStateException", "Record", "Enum",
})

MAX_EXAMPLE_CLASSES = 3


class GapKind(StrEnum):
    ANNOTATION = "annotation"
    SUPERTYPE = "supertype"


@dataclass(frozen=True, slots=True)
class KnowledgeGap:
    """Algo que el proyecto usa y para lo que no tenemos concepto (no genera preguntas)."""

    kind: GapKind
    name: str  # nombre simple: "Data"
    qualified_name: str | None  # según los imports: "lombok.Data" (None si no se puede saber)
    usages: int
    classes: tuple[str, ...]  # algunas clases donde aparece (nombres cualificados)

    @property
    def display(self) -> str:
        return f"@{self.name}" if self.kind is GapKind.ANNOTATION else self.name


@dataclass(frozen=True, slots=True)
class ConceptUsage:
    concept: Concept
    usages: int


@dataclass(frozen=True, slots=True)
class KnowledgeReport:
    used: tuple[ConceptUsage, ...]  # de más a menos usado
    gaps: tuple[KnowledgeGap, ...]

    @property
    def known_count(self) -> int:
        return len(self.used)

    @property
    def total_count(self) -> int:
        return len(self.used) + len(self.gaps)


def build_report(model: ProjectModel, kb: KnowledgeBase) -> KnowledgeReport:
    project_types = {c.name for c in model.classes}
    project_annotations = {c.name for c in model.classes if c.kind is TypeKind.ANNOTATION}

    concept_usages: Counter[str] = Counter()
    gap_usages: Counter[tuple[GapKind, str]] = Counter()
    gap_classes: dict[tuple[GapKind, str], list[str]] = defaultdict(list)
    gap_imports: dict[tuple[GapKind, str], str] = {}

    for cls in model.main_classes:
        for kind, name in _references(cls):
            concept = kb.for_annotation(name) if kind is GapKind.ANNOTATION else kb.for_supertype(name)
            if concept is not None:
                concept_usages[concept.id] += 1
                continue
            if not _is_teachable(kind, name, cls, project_types, project_annotations):
                continue
            key = (kind, name)
            gap_usages[key] += 1
            if cls.qualified_name not in gap_classes[key]:
                gap_classes[key].append(cls.qualified_name)
            if key not in gap_imports and (imported := _imported_as(cls, name)):
                gap_imports[key] = imported

    used = tuple(ConceptUsage(kb.get(cid), n) for cid, n in concept_usages.most_common())
    gaps = tuple(
        KnowledgeGap(kind, name, gap_imports.get((kind, name)), n,
                     tuple(gap_classes[(kind, name)][:MAX_EXAMPLE_CLASSES]))
        for (kind, name), n in sorted(gap_usages.items(), key=lambda item: (-item[1], item[0][1]))
    )
    return KnowledgeReport(used, gaps)


def _references(cls: JavaClass) -> Iterator[tuple[GapKind, str]]:
    for ann in cls.annotations:
        yield GapKind.ANNOTATION, ann.name
    for f in cls.fields:
        for ann in f.annotations:
            yield GapKind.ANNOTATION, ann.name
    for m in cls.methods:
        for ann in m.annotations:
            yield GapKind.ANNOTATION, ann.name
        for p in m.parameters:
            for ann in p.annotations:
                yield GapKind.ANNOTATION, ann.name
    for supertype in (*cls.interfaces, *([cls.superclass] if cls.superclass else [])):
        yield GapKind.SUPERTYPE, simple_type_name(supertype)


def _is_teachable(kind: GapKind, name: str, cls: JavaClass, project_types: set[str],
                  project_annotations: set[str]) -> bool:
    """Descarta lo que no es conocimiento de framework: tipos propios y básicos de Java."""
    if kind is GapKind.ANNOTATION:
        return name not in IGNORED_ANNOTATIONS and name not in project_annotations
    if name in project_types or name in JAVA_BASIC_TYPES:
        return False
    imported = _imported_as(cls, name)
    return not (imported and imported.startswith("java."))


def _imported_as(cls: JavaClass, name: str) -> str | None:
    return next((i for i in cls.imports if i.rsplit(".", 1)[-1] == name), None)
