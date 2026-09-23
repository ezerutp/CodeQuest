"""Caso de uso: completar la base de conocimiento con IA y gestionar los conceptos generados."""

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from codequest.core.ai.base import AIError, AIErrorKind, AIProvider
from codequest.core.ai.concept_generator import ConceptGenerator, describe_gap
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.coverage import KnowledgeGap
from codequest.core.knowledge.models import Concept, ConceptSource
from codequest.core.knowledge.store import KnowledgeStore

log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]

# Errores que afectarán igual a todos los huecos restantes: no tiene sentido seguir.
_STOP_KINDS = frozenset({AIErrorKind.AUTH, AIErrorKind.RATE_LIMIT, AIErrorKind.NETWORK})


@dataclass
class GenerationResult:
    created: list[Concept] = field(default_factory=list)
    failed: list[tuple[KnowledgeGap, str]] = field(default_factory=list)
    cancelled: bool = False


class KnowledgeService:
    def __init__(self, kb: KnowledgeBase, store: KnowledgeStore | None, provider: AIProvider | None) -> None:
        self.kb = kb
        self._store = store
        self._provider = provider
        self._generator = ConceptGenerator(provider) if provider else None

    @property
    def can_generate(self) -> bool:
        return self._generator is not None and self._store is not None

    @property
    def provider_name(self) -> str | None:
        return self._provider.name if self._provider else None

    @staticmethod
    def privacy_preview(gaps: Sequence[KnowledgeGap]) -> list[str]:
        """Lo que se enviará a la IA, tal cual, para pedir confirmación al usuario."""
        return [describe_gap(gap) for gap in gaps]

    def generate(self, gaps: Sequence[KnowledgeGap], on_progress: ProgressCallback | None = None,
                 cancel: threading.Event | None = None) -> GenerationResult:
        """Genera y guarda conceptos. Se ejecuta en un worker: no modifica `self.kb`
        (lo usa la UI en el hilo principal); después hay que llamar a `register()`."""
        if not self.can_generate:
            raise AIError(AIErrorKind.UNAVAILABLE)
        result = GenerationResult()
        for index, gap in enumerate(gaps):
            if cancel is not None and cancel.is_set():
                result.cancelled = True
                break
            if on_progress:
                on_progress(index, len(gaps))
            try:
                concept = self._generator.generate(gap)
                self._store.save(concept)
                result.created.append(concept)
            except AIError as exc:
                log.info("No se generó %s: %s", gap.display, exc)
                detailed = exc.kind in (AIErrorKind.INVALID_OUTPUT, AIErrorKind.SERVICE)
                result.failed.append((gap, str(exc) if detailed else exc.user_message))
                if exc.kind in _STOP_KINDS:
                    result.failed.extend((g, "No se intentó.") for g in gaps[index + 1:])
                    break
            except OSError as exc:
                log.warning("No se pudo guardar el concepto de %s: %s", gap.display, exc)
                result.failed.append((gap, f"No se pudo guardar: {exc}"))
            except Exception:  # fallo inesperado con un elemento: no debe abortar el resto del lote
                log.exception("Error inesperado generando %s", gap.display)
                result.failed.append((gap, "Error inesperado; revisa el log de CodeQuest."))
        if on_progress:
            on_progress(len(gaps), len(gaps))
        return result

    def register(self, concepts: Sequence[Concept]) -> None:
        """Hilo principal: incorpora a la base los conceptos recién generados."""
        for concept in concepts:
            self.kb.add(concept)

    def delete(self, concept_id: str) -> bool:
        """Borra un concepto generado con IA. Los del usuario los gestiona él en su carpeta
        (su archivo puede no llamarse como el id), y los integrados no se borran."""
        concept = self.kb.get(concept_id)
        if concept is None or concept.source is not ConceptSource.AI:
            return False
        self.kb.remove(concept_id)
        if self._store is not None:
            try:
                self._store.delete(concept_id)
            except OSError as exc:
                log.warning("No se pudo borrar el archivo de %s: %s", concept_id, exc)
        return True
