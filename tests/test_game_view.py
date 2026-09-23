"""Flujo de la vista de juego con un QApplication offscreen."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from codequest.core.analysis.snippets import CodeSnippet, SnippetRef  # noqa: E402
from codequest.core.games.base import GameSession  # noqa: E402
from codequest.core.games.multiple_choice import MultipleChoiceMode  # noqa: E402
from codequest.core.knowledge.base import KnowledgeBase  # noqa: E402
from codequest.core.questions.models import Question  # noqa: E402
from codequest.ui.pages.learn.game_view import GameView  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _session() -> GameSession:
    concept = KnowledgeBase.default().for_annotation("Transactional")
    questions = [
        Question(key=f"q{i}", prompt="¿Qué hace `@Transactional`?", concept=concept, class_name="C",
                 snippet=SnippetRef("A.java", 3, 4, (3,)), choices=("a", "b", "c", "d"), correct_index=2)
        for i in range(2)
    ]
    return GameSession(MultipleChoiceMode(), questions)


def _view(loaded: list[SnippetRef]) -> GameView:
    def load(ref: SnippetRef) -> CodeSnippet:
        loaded.append(ref)
        return CodeSnippet(ref.file, ref.start_line, ref.end_line, "@Transactional\nvoid m() {}")

    return GameView(load)


def test_wrong_answer_marks_choices_and_shows_explanation(qapp: QApplication) -> None:
    loaded: list[SnippetRef] = []
    view = _view(loaded)
    session = _session()
    view.start(session, None)

    view._answer(0)

    states = [c.property("state") for c in view._choices]
    assert states == ["incorrect", "dimmed", "correct", "dimmed"]
    assert not view._feedback.isHidden() and not view._next.isHidden()
    assert "C" in view._feedback._title.text()  # "La respuesta correcta es la C"
    assert loaded == [SnippetRef("A.java", 3, 4, (3,))]
    assert view._editor.first_line == 3


def test_answer_is_locked_until_next(qapp: QApplication) -> None:
    view = _view([])
    session = _session()
    view.start(session, None)

    view._answer(2)
    view._answer(0)  # ignorado: ya respondida
    view._skip()  # ignorado

    assert session.correct_count == 1 and len(session.results) == 1


def test_dont_know_then_finish(qapp: QApplication) -> None:
    view = _view([])
    session = _session()
    finished: list[GameSession] = []
    view.finished.connect(finished.append)
    view.start(session, "User")

    view._skip()
    view._go_next()
    view._answer(2)
    assert view._next.text() == "Ver resultados"
    view._go_next()

    assert finished == [session] and session.is_finished
    assert [e.outcome.value for e in session.results] == ["skipped", "correct"]


def test_unreadable_snippet_does_not_break_the_round(qapp: QApplication) -> None:
    def failing(ref: SnippetRef) -> CodeSnippet:
        raise OSError("archivo borrado")

    view = GameView(failing)
    view.start(_session(), None)

    assert "archivo borrado" in view._editor.code()
