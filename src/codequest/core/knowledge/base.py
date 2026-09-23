"""Base de conocimiento por capas: integrada (prioritaria) + carpeta del usuario."""

import logging
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from codequest.core.knowledge.loader import LoadIssue, load_builtin, load_directory
from codequest.core.knowledge.models import Concept, ConceptSource

log = logging.getLogger(__name__)


class KnowledgeBase:
    def __init__(self, concepts: Iterable[Concept], issues: Iterable[LoadIssue] = ()) -> None:
        """Las capas llegan en orden de prioridad. Un id o una anotación ya reclamados por un
        concepto anterior se descartan: el contenido integrado no puede ser reemplazado."""
        self._concepts: dict[str, Concept] = {}
        self._by_annotation: dict[str, Concept] = {}
        self._by_supertype: dict[str, Concept] = {}
        self.issues: list[LoadIssue] = list(issues)
        for concept in concepts:
            self._add(concept)

    @classmethod
    def default(cls) -> "KnowledgeBase":
        """Solo el conocimiento integrado (tests, o cuando no hay carpeta de usuario)."""
        return cls(load_builtin())

    @classmethod
    def load(cls, user_directory: Path | None) -> "KnowledgeBase":
        builtin = load_builtin()
        if user_directory is None:
            return cls(builtin)
        user, issues = load_directory(user_directory)
        kb = cls([*builtin, *user], issues)
        log.info("Conocimiento: %s", dict(kb.source_counts()))
        return kb

    @property
    def concepts(self) -> tuple[Concept, ...]:
        return tuple(self._concepts.values())

    def get(self, concept_id: str) -> Concept | None:
        return self._concepts.get(concept_id)

    def for_annotation(self, name: str) -> Concept | None:
        return self._by_annotation.get(name)

    def for_supertype(self, name: str) -> Concept | None:
        return self._by_supertype.get(name)

    def source_counts(self) -> Counter[ConceptSource]:
        return Counter(c.source for c in self._concepts.values())

    def _add(self, concept: Concept) -> None:
        conflicts = [f"id '{concept.id}'"] if concept.id in self._concepts else []
        conflicts += [f"@{a}" for a in concept.matches.annotations if a in self._by_annotation]
        conflicts += [s for s in concept.matches.supertypes if s in self._by_supertype]
        if conflicts:
            if concept.source is ConceptSource.BUILTIN:
                raise ValueError(f"Conocimiento integrado duplicado en {concept.id}: {', '.join(conflicts)}")
            message = f"ya existe un concepto para {', '.join(conflicts)}; se usa el existente"
            log.warning("Concepto %s ignorado: %s", concept.id, message)
            self.issues.append(LoadIssue(concept.id, message))
            return
        self._concepts[concept.id] = concept
        for name in concept.matches.annotations:
            self._by_annotation[name] = concept
        for name in concept.matches.supertypes:
            self._by_supertype[name] = concept
