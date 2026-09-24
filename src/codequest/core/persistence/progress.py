"""Progreso del estudiante: proyectos, sesiones e intentos. Nunca guarda código."""

import hashlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from codequest.core.games.base import Evaluation, Outcome
from codequest.core.persistence.database import Database
from codequest.core.project.models import ProjectInfo

# "Dominas un concepto cuando aciertas sus últimas MASTERY_WINDOW preguntas."
MASTERY_WINDOW = 3

Clock = Callable[[], datetime]


def project_id_for(info: ProjectInfo) -> str:
    """Identidad estable del proyecto: la ruta canónica. No se escribe nada en el repo del usuario."""
    return hashlib.sha256(str(info.root.resolve()).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class ConceptProgress:
    concept_id: str
    attempts: int
    correct: int
    recent: tuple[Outcome, ...]  # últimos resultados, del más antiguo al más reciente
    last_seen: str

    @property
    def mastery(self) -> float:
        """Aciertos entre los últimos MASTERY_WINDOW intentos (0 a 1)."""
        window = self.recent[-MASTERY_WINDOW:]
        return sum(o is Outcome.CORRECT for o in window) / MASTERY_WINDOW

    @property
    def is_mastered(self) -> bool:
        return self.mastery >= 1.0

    @property
    def last_outcome(self) -> Outcome:
        return self.recent[-1]


@dataclass(frozen=True, slots=True)
class ProjectHistory:
    concepts: dict[str, ConceptProgress]
    sessions: int
    attempts: int
    correct: int
    last_session_at: str | None
    last_scope: str | None

    @property
    def accuracy(self) -> float:
        return self.correct / self.attempts if self.attempts else 0.0

    @property
    def has_history(self) -> bool:
        return self.attempts > 0


@dataclass(frozen=True, slots=True)
class SessionSummary:
    started_at: str
    mode: str
    scope: str | None
    answered: int
    correct: int


class ProgressRepository:
    def __init__(self, db: Database, clock: Clock | None = None) -> None:
        self._db = db
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    def open_project(self, info: ProjectInfo) -> str:
        project_id = project_id_for(info)
        now = self._now()
        with self._db.connection as conn:
            conn.execute(
                """INSERT INTO projects (id, name, root_path, git_remote, first_seen, last_opened)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name = excluded.name, git_remote = excluded.git_remote,
                                                 last_opened = excluded.last_opened""",
                (project_id, info.name, str(info.root), info.git_remote, now, now),
            )
        return project_id

    def start_session(self, project_id: str, mode: str, scope: str | None, total: int) -> int:
        with self._db.connection as conn:
            cursor = conn.execute(
                "INSERT INTO sessions (project_id, mode, scope, total, started_at) VALUES (?, ?, ?, ?, ?)",
                (project_id, mode, scope, total, self._now()),
            )
        return int(cursor.lastrowid)

    def record_attempt(self, project_id: str, session_id: int, evaluation: Evaluation) -> None:
        question = evaluation.question
        with self._db.connection as conn:
            conn.execute(
                """INSERT INTO attempts (session_id, project_id, question_key, concept_id, class_name,
                                         outcome, answered_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, project_id, question.key, question.concept.id, question.class_name,
                 evaluation.outcome.value, self._now()),
            )

    def finish_session(self, session_id: int) -> None:
        with self._db.connection as conn:
            conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (self._now(), session_id))

    def history(self, project_id: str) -> ProjectHistory:
        conn = self._db.connection
        rows = conn.execute(
            "SELECT concept_id, outcome, answered_at FROM attempts WHERE project_id = ? ORDER BY answered_at, id",
            (project_id,),
        ).fetchall()
        by_concept: dict[str, list[tuple[Outcome, str]]] = defaultdict(list)
        for row in rows:
            by_concept[row["concept_id"]].append((Outcome(row["outcome"]), row["answered_at"]))
        concepts = {
            cid: ConceptProgress(
                concept_id=cid,
                attempts=len(items),
                correct=sum(o is Outcome.CORRECT for o, _ in items),
                recent=tuple(o for o, _ in items[-MASTERY_WINDOW:]),
                last_seen=items[-1][1],
            )
            for cid, items in by_concept.items()
        }
        last = conn.execute(
            """SELECT started_at, scope FROM sessions
               WHERE project_id = ? AND id IN (SELECT DISTINCT session_id FROM attempts WHERE project_id = ?)
               ORDER BY started_at DESC, id DESC LIMIT 1""",
            (project_id, project_id),
        ).fetchone()
        sessions = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM attempts WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        return ProjectHistory(
            concepts=concepts,
            sessions=sessions,
            attempts=len(rows),
            correct=sum(c.correct for c in concepts.values()),
            last_session_at=last["started_at"] if last else None,
            last_scope=last["scope"] if last else None,
        )

    def recent_sessions(self, project_id: str, limit: int = 10) -> list[SessionSummary]:
        """Sesiones con al menos una respuesta, de la más reciente a la más antigua."""
        rows = self._db.connection.execute(
            """SELECT s.started_at, s.mode, s.scope, COUNT(a.id) AS answered,
                      SUM(a.outcome = 'correct') AS correct
               FROM sessions s JOIN attempts a ON a.session_id = s.id
               WHERE s.project_id = ?
               GROUP BY s.id ORDER BY s.started_at DESC, s.id DESC LIMIT ?""",
            (project_id, limit),
        ).fetchall()
        return [SessionSummary(r["started_at"], r["mode"], r["scope"], r["answered"], r["correct"] or 0)
                for r in rows]

    def recent_question_keys(self, project_id: str, limit: int = 30) -> frozenset[str]:
        rows = self._db.connection.execute(
            "SELECT question_key FROM attempts WHERE project_id = ? ORDER BY answered_at DESC, id DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return frozenset(row[0] for row in rows)

    def reset_project(self, project_id: str) -> None:
        with self._db.connection as conn:
            conn.execute("DELETE FROM sessions WHERE project_id = ?", (project_id,))


def concept_priorities(history: ProjectHistory, concept_ids: Iterable[str]) -> dict[str, float]:
    """Orden de práctica (menor = antes): falladas recientemente < sin practicar < dominadas."""
    priorities: dict[str, float] = {}
    for cid in concept_ids:
        progress = history.concepts.get(cid)
        if progress is None:
            priorities[cid] = 1.0
        elif progress.is_mastered:
            priorities[cid] = 3.0
        elif progress.last_outcome is not Outcome.CORRECT:
            priorities[cid] = progress.mastery  # 0 a 0.67: lo que más cuesta, primero
        else:
            priorities[cid] = 2.0 + progress.mastery  # en progreso y la última fue acierto
    return priorities
