import random
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from codequest.core.analysis.snippets import SnippetRef
from codequest.core.games.base import Evaluation, GameSession, Outcome
from codequest.core.games.multiple_choice import MultipleChoiceMode
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.coverage import build_report
from codequest.core.persistence.database import MIGRATIONS, Database
from codequest.core.persistence.progress import (
    ConceptProgress,
    ProgressRepository,
    concept_priorities,
    project_id_for,
)
from codequest.core.project.models import ProjectInfo
from codequest.core.questions.generator import QuestionGenerator
from codequest.core.questions.models import Question
from codequest.services.progress_service import ProgressService
from codequest.services.project_service import ProjectService

KB = KnowledgeBase.default()
C = Outcome.CORRECT
X = Outcome.INCORRECT
S = Outcome.SKIPPED


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


def _question(concept_id: str, key: str | None = None) -> Question:
    concept = KB.get(concept_id)
    return Question(key=key or f"{concept_id}:app.C", prompt="?", concept=concept, class_name="app.C",
                    snippet=SnippetRef("C.java", 1, 1), choices=("a", "b", "c", "d"), correct_index=0)


def _eval(concept_id: str, outcome: Outcome, key: str | None = None) -> Evaluation:
    return Evaluation(_question(concept_id, key), outcome, 0 if outcome is C else None)


@pytest.fixture
def repo() -> ProgressRepository:
    return ProgressRepository(Database(":memory:"), clock=Clock())


INFO = ProjectInfo(root=Path("/tmp/shop"), name="shop", git_remote="https://github.com/me/shop.git")


def _play(repo: ProgressRepository, results: list[tuple[str, Outcome]], project: ProjectInfo = INFO) -> str:
    project_id = repo.open_project(project)
    session = repo.start_session(project_id, "multiple_choice", None, len(results))
    for concept_id, outcome in results:
        repo.record_attempt(project_id, session, _eval(concept_id, outcome))
    repo.finish_session(session)
    return project_id


# --- base de datos ------------------------------------------------------------------

def test_migrations_create_schema_and_are_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "data" / "codequest.db"
    db = Database(path)
    assert db.version == len(MIGRATIONS)
    db.close()

    reopened = Database(path)  # no vuelve a migrar
    tables = {r[0] for r in reopened.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"projects", "sessions", "attempts"} <= tables


def test_refuses_database_from_newer_version(tmp_path: Path) -> None:
    path = tmp_path / "codequest.db"
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    conn.close()
    with pytest.raises(sqlite3.DatabaseError, match="más nueva"):
        Database(path)


def test_schema_never_stores_code(repo: ProgressRepository) -> None:
    _play(repo, [("spring.transactional", C)])
    columns = {row[1] for table in ("projects", "sessions", "attempts")
               for row in repo._db.connection.execute(f"PRAGMA table_info({table})")}
    assert not columns & {"code", "snippet", "text", "source"}


# --- repositorio ----------------------------------------------------------------------

def test_project_identity_is_the_canonical_path() -> None:
    assert project_id_for(INFO) == project_id_for(ProjectInfo(root=Path("/tmp/../tmp/shop"), name="otro"))
    assert project_id_for(INFO) != project_id_for(ProjectInfo(root=Path("/tmp/otro"), name="shop"))


def test_reopening_a_project_keeps_its_history(repo: ProgressRepository) -> None:
    first = _play(repo, [("spring.transactional", C)])
    assert repo.open_project(INFO) == first
    assert repo.history(first).attempts == 1


def test_history_summarizes_attempts(repo: ProgressRepository) -> None:
    pid = _play(repo, [("spring.transactional", X), ("spring.transactional", C), ("jpa.entity", S)])

    history = repo.history(pid)

    assert (history.attempts, history.correct, history.sessions) == (3, 1, 1)
    assert history.concepts["spring.transactional"].recent == (X, C)
    assert history.last_session_at is not None and history.last_scope is None


def test_projects_are_isolated(repo: ProgressRepository) -> None:
    _play(repo, [("spring.transactional", C)])
    other = _play(repo, [("jpa.entity", X)], ProjectInfo(root=Path("/tmp/otro"), name="otro"))
    assert set(repo.history(other).concepts) == {"jpa.entity"}


def test_recent_question_keys(repo: ProgressRepository) -> None:
    pid = repo.open_project(INFO)
    session = repo.start_session(pid, "multiple_choice", None, 3)
    for key in ("k1", "k2", "k3"):
        repo.record_attempt(pid, session, _eval("spring.transactional", C, key))
    assert repo.recent_question_keys(pid, limit=2) == {"k2", "k3"}


def test_reset_project_deletes_its_attempts(repo: ProgressRepository) -> None:
    pid = _play(repo, [("spring.transactional", C)])
    repo.reset_project(pid)
    assert repo.history(pid).attempts == 0


# --- dominio y prioridades --------------------------------------------------------------

@pytest.mark.parametrize(("recent", "mastery", "mastered"), [
    ((C,), 1 / 3, False),
    ((X, C, C), 2 / 3, False),
    ((C, C, C), 1.0, True),
    ((C, C, X), 2 / 3, False),  # un fallo reciente quita el dominio
    ((S, S, S), 0.0, False),
])
def test_mastery_is_correct_share_of_last_three(recent, mastery, mastered) -> None:
    progress = ConceptProgress("x", len(recent), recent.count(C), recent, "t")
    assert progress.mastery == pytest.approx(mastery) and progress.is_mastered is mastered


def test_priorities_order_weak_then_new_then_mastered(repo: ProgressRepository) -> None:
    pid = _play(repo, [
        ("spring.transactional", X),                                      # fallado
        ("jpa.entity", C), ("jpa.entity", C), ("jpa.entity", C),          # dominado
        ("jpa.id", X), ("jpa.id", C),                                     # en progreso, último acierto
    ])
    priorities = concept_priorities(repo.history(pid), ["spring.transactional", "jpa.entity", "jpa.id", "jpa.table"])

    ordered = sorted(priorities, key=priorities.get)
    assert ordered == ["spring.transactional", "jpa.table", "jpa.id", "jpa.entity"]


def test_generator_follows_priorities_and_avoids_recent(shop_project: Path) -> None:
    service = ProjectService()
    model = service.analyze(service.detect(shop_project))
    generator = QuestionGenerator(KB)
    drafts = generator.drafts(model)
    ids = {d.concept.id for d in drafts}
    priorities = {cid: 1.0 for cid in ids} | {"spring.path-variable": 0.0, "spring.transactional": 9.0}

    questions = generator.generate(model, limit=len(ids), rng=random.Random(1), priorities=priorities)
    assert questions[0].concept.id == "spring.path-variable"
    assert questions[-1].concept.id == "spring.transactional"

    path_keys = [d.key for d in drafts if d.concept.id == "spring.path-variable"]
    assert len(path_keys) >= 2
    seen = frozenset(path_keys[:-1])
    first = generator.generate(model, limit=1, rng=random.Random(1), priorities=priorities, avoid_keys=seen)[0]
    assert first.key == path_keys[-1]  # la no vista recientemente va primero


# --- servicio -----------------------------------------------------------------------------

def _game(*concepts: str) -> GameSession:
    return GameSession(MultipleChoiceMode(), [_question(c) for c in concepts])


def test_overview_percent_and_weak_concepts(shop_project: Path) -> None:
    service = ProjectService()
    model = service.analyze(service.detect(shop_project))
    report = build_report(model, KB)
    progress = ProgressService(ProgressRepository(Database(":memory:"), clock=Clock()))
    progress.open_project(model.info)

    empty = progress.overview(report)
    assert (empty.percent, empty.practiced, empty.has_history) == (0, 0, False)

    game = _game("spring.transactional", "spring.transactional", "spring.transactional", "jpa.entity", "jpa.id")
    progress.start(game)
    for concept_id, outcome in [("spring.transactional", C)] * 3 + [("jpa.entity", X), ("jpa.id", C)]:
        progress.record(_eval(concept_id, outcome))
    progress.finish()

    overview = progress.overview(report)
    assert (overview.mastered, overview.practiced, overview.total) == (1, 3, report.known_count)
    assert overview.percent == round(100 * (1.0 + 1 / 3) / report.known_count)
    # jpa.id lleva 1 de 3 pero su última respuesta fue un acierto: no "te cuesta".
    assert [c.id for c in overview.weak] == ["jpa.entity"]
    assert overview.has_history and overview.history.accuracy == pytest.approx(0.8)


def test_empty_rounds_do_not_create_sessions() -> None:
    repo = ProgressRepository(Database(":memory:"), clock=Clock())
    progress = ProgressService(repo)
    progress.open_project(INFO)
    progress.start(_game())
    progress.finish()
    assert repo._db.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_database_errors_disable_saving_but_never_raise() -> None:
    db = Database(":memory:")
    progress = ProgressService(ProgressRepository(db, clock=Clock()))
    progress.open_project(INFO)
    progress.start(_game("jpa.entity"))
    db.close()  # simula un disco que falla

    progress.record(_eval("jpa.entity", C))  # no lanza
    assert not progress.available and progress.error
    assert progress.history().attempts == 0 and progress.recent_keys() == frozenset()


def test_service_without_database() -> None:
    progress = ProgressService(None, error="sin permisos")
    progress.open_project(INFO)
    progress.record(_eval("jpa.entity", C))
    assert not progress.available and progress.error == "sin permisos"
