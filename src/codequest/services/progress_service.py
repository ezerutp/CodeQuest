"""Caso de uso: registrar lo que practica el estudiante y resumir su progreso.

Si la base de datos falla (disco lleno, archivo bloqueado…), el guardado se desactiva y el
juego continúa: perder el historial nunca debe impedir practicar.
"""

import functools
import logging
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, TypeVar

from codequest.core.games.base import Evaluation, GameSession, Outcome
from codequest.core.knowledge.coverage import KnowledgeReport
from codequest.core.knowledge.models import Concept
from codequest.core.persistence.progress import (
    ConceptProgress,
    ProgressRepository,
    ProjectHistory,
    concept_priorities,
)
from codequest.core.project.models import ProjectInfo

log = logging.getLogger(__name__)

MAX_WEAK = 5
T = TypeVar("T")

_EMPTY_HISTORY = ProjectHistory(concepts={}, sessions=0, attempts=0, correct=0, last_session_at=None,
                                last_scope=None)


@dataclass(frozen=True, slots=True)
class ProgressOverview:
    percent: int  # dominio medio de los conceptos que usa el proyecto
    mastered: int
    practiced: int
    total: int  # conceptos que usa el proyecto
    weak: tuple[Concept, ...]  # la última respuesta fue un fallo o "No sé"; los que más cuestan primero
    history: ProjectHistory

    @property
    def has_history(self) -> bool:
        return self.history.has_history


def _safe(default: Any = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(method: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(method)
        def wrapper(self: "ProgressService", *args: Any, **kwargs: Any) -> T:
            if self._repo is None:
                return default
            try:
                return method(self, *args, **kwargs)
            except sqlite3.Error as exc:
                log.warning("Progreso desactivado por un error de la base de datos: %s", exc)
                self.error = str(exc)
                self._repo = None
                return default
        return wrapper
    return decorator


class ProgressService:
    def __init__(self, repo: ProgressRepository | None, error: str | None = None) -> None:
        self._repo = repo
        self.error = error  # motivo si el guardado no está disponible
        self._project_id: str | None = None
        self._session_id: int | None = None
        self._game: GameSession | None = None

    @property
    def available(self) -> bool:
        return self._repo is not None

    @_safe()
    def open_project(self, info: ProjectInfo) -> None:
        self._project_id = None
        self._session_id = None
        self._project_id = self._repo.open_project(info)

    @_safe()
    def start(self, game: GameSession) -> None:
        self._game = game
        self._session_id = None
        if self._project_id is not None and game.questions:
            self._session_id = self._repo.start_session(self._project_id, game.mode.mode_id, game.scope, game.total)

    @_safe()
    def record(self, evaluation: Evaluation) -> None:
        if self._project_id is not None and self._session_id is not None:
            self._repo.record_attempt(self._project_id, self._session_id, evaluation)

    @_safe()
    def finish(self) -> None:
        if self._session_id is not None:
            self._repo.finish_session(self._session_id)
            self._session_id = None

    @_safe(default=_EMPTY_HISTORY)
    def history(self) -> ProjectHistory:
        return self._repo.history(self._project_id) if self._project_id else _EMPTY_HISTORY

    @_safe(default=frozenset())
    def recent_keys(self) -> frozenset[str]:
        return self._repo.recent_question_keys(self._project_id) if self._project_id else frozenset()

    def priorities(self, concept_ids: Iterable[str]) -> dict[str, float]:
        return concept_priorities(self.history(), concept_ids)

    def overview(self, report: KnowledgeReport) -> ProgressOverview:
        history = self.history()
        used = [u.concept for u in report.used]
        progress: list[tuple[Concept, ConceptProgress | None]] = [(c, history.concepts.get(c.id)) for c in used]
        masteries = [p.mastery if p else 0.0 for _, p in progress]
        # "Te cuesta" solo si la última vez fallaste: un acierto reciente no es una debilidad,
        # aunque todavía no llegue al dominio completo.
        weak = [(c, p) for c, p in progress if p and p.last_outcome is not Outcome.CORRECT]
        weak.sort(key=lambda item: item[1].last_seen, reverse=True)  # a igual dominio, lo más reciente
        weak.sort(key=lambda item: item[1].mastery)  # sort estable: primero lo que más cuesta
        return ProgressOverview(
            percent=round(100 * sum(masteries) / len(masteries)) if masteries else 0,
            mastered=sum(1 for _, p in progress if p and p.is_mastered),
            practiced=sum(1 for _, p in progress if p),
            total=len(used),
            weak=tuple(c for c, _ in weak[:MAX_WEAK]),
            history=history,
        )

    @_safe()
    def reset(self) -> None:
        if self._project_id is not None:
            self._repo.reset_project(self._project_id)

