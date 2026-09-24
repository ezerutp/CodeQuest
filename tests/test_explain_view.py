"""Vista del modo "Explícame este código" con un QApplication offscreen."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from codequest.core.ai.explanation_grader import ExplanationFeedback, Verdict  # noqa: E402
from codequest.core.analysis.snippets import CodeSnippet, SnippetRef  # noqa: E402
from codequest.core.games.base import GameSession, Outcome  # noqa: E402
from codequest.core.games.explain_code import ExplainCodeMode  # noqa: E402
from codequest.core.knowledge.base import KnowledgeBase  # noqa: E402
from codequest.core.questions.models import Question  # noqa: E402
from codequest.ui.pages.learn.explain_view import ExplainCodeView  # noqa: E402

ANSWER = "Es un endpoint GET que recibe el id en la URL y devuelve el usuario encontrado."


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _session() -> GameSession:
    concept = KnowledgeBase.default().for_annotation("GetMapping")
    questions = [Question(key=f"q{i}", prompt="Explica `get()`", concept=concept, class_name="C",
                          snippet=SnippetRef("C.java", 1, 4)) for i in range(2)]
    return GameSession(ExplainCodeMode(), questions)


def _view() -> ExplainCodeView:
    return ExplainCodeView(lambda ref: CodeSnippet(ref.file, 1, 4, "a\nb\nc\nd"))


def _feedback(verdict: Verdict = Verdict.PARTIAL) -> ExplanationFeedback:
    return ExplanationFeedback(verdict, "Vas bien.", ("GET",), ("`@PathVariable`",), (), "Modelo.")


def test_short_answer_is_not_submitted(qapp: QApplication) -> None:
    view, sent = _view(), []
    view.submitted.connect(lambda q, text: sent.append(text))
    view.start(_session(), None)

    view._answer.setPlainText("no sé")
    view._submit()
    assert sent == [] and "detalle" in view._hint.text()

    view._answer.setPlainText(ANSWER)
    view._submit()
    assert sent == [ANSWER]


def test_feedback_records_partial_and_shows_lists(qapp: QApplication) -> None:
    view, answered = _view(), []
    view.answered.connect(answered.append)
    session = _session()
    view.start(session, None)

    view.show_grading("q0")
    assert view._answer.isReadOnly() and not view._submit_button.isEnabled()
    view.apply_feedback("q0", _feedback())

    assert [e.outcome for e in answered] == [Outcome.PARTIAL]
    assert not view._feedback.isHidden() and not view._next.isHidden()
    assert view._lists_layout.count() == 4  # 2 títulos + 2 puntos


def test_late_feedback_for_another_exercise_is_discarded(qapp: QApplication) -> None:
    view = _view()
    session = _session()
    view.start(session, None)
    view._skip()
    view._go_next()

    view.apply_feedback("q0", _feedback(Verdict.CORRECT))

    assert len(session.results) == 1 and session.results[0].outcome is Outcome.SKIPPED


def test_grading_error_lets_the_student_retry(qapp: QApplication) -> None:
    view = _view()
    view.start(_session(), None)
    view.show_grading("q0")

    view.show_grading_error("q0", "Sin conexión.")

    assert not view._answer.isReadOnly() and view._submit_button.isEnabled()
    assert "Sin conexión." in view._hint.text()
