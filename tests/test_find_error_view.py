"""Flujo de "Encuentra el error" con un QApplication offscreen."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from codequest.core.analysis.snippets import CodeSnippet, SnippetRef  # noqa: E402
from codequest.core.games.base import GameSession, Outcome  # noqa: E402
from codequest.core.games.find_error import FindErrorMode  # noqa: E402
from codequest.core.knowledge.base import KnowledgeBase  # noqa: E402
from codequest.core.questions.models import CodeMutation, Question  # noqa: E402
from codequest.ui.pages.learn.find_error_view import FindErrorView  # noqa: E402
from codequest.ui.theme import current_palette  # noqa: E402

CODE = '@GetMapping("/{id}")\npublic User get(@PathVariable Long id) {\n    return service.find(id);\n}'


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _session(code_line: int = 20) -> GameSession:
    concept = KnowledgeBase.default().for_annotation("GetMapping")
    mutation = CodeMutation(line=code_line, find="@GetMapping", replace="@PostMapping", explanation="`get()` consulta.")
    questions = [Question(key=f"q{i}", prompt="¿Dónde está el error?", concept=concept, class_name="C",
                          snippet=SnippetRef("A.java", 20, 23), mutation=mutation) for i in range(2)]
    return GameSession(FindErrorMode(), questions)


def _view(text: str = CODE) -> FindErrorView:
    return FindErrorView(lambda ref: CodeSnippet(ref.file, ref.start_line, ref.end_line, text))


def test_shows_the_mutated_copy_with_real_line_numbers(qapp: QApplication) -> None:
    view = _view()
    view.start(_session(), None)
    assert view._editor.code().splitlines()[0] == '@PostMapping("/{id}")'
    assert view._editor.first_line == 20
    assert view.selected_line is None and not view._check.isEnabled()  # cargar no cuenta como elegir


def test_clicking_a_line_selects_it_and_wrong_answer_marks_both_lines(qapp: QApplication) -> None:
    view = _view()
    session = _session()
    view.start(session, None)
    evaluations = []
    view.answered.connect(evaluations.append)

    view._editor.scroll_to_line(22)  # mueve el cursor como un clic
    assert view.selected_line == 22 and view._check.isEnabled()
    view._answer()

    palette = current_palette()
    assert evaluations[0].outcome is Outcome.INCORRECT and evaluations[0].answer == 22
    assert view._editor._highlighted == {20: palette.success_soft, 22: palette.danger_soft}
    assert view._feedback._original.text() == '@GetMapping("/{id}")'
    assert view._feedback._mutated.text() == '@PostMapping("/{id}")'
    assert "línea 20" in view._feedback._title.text()

    view.select_line(21)  # ya respondió: no cambia nada
    assert view.selected_line == 22


def test_correct_answer_and_round_end(qapp: QApplication) -> None:
    view = _view()
    session = _session()
    view.start(session, None)
    finished = []
    view.finished.connect(finished.append)
    view.select_line(20)
    view._confirm()
    assert session.results[-1].outcome is Outcome.CORRECT
    view._confirm()  # Enter tras responder = Siguiente
    view._skip()
    assert view._next.text() == "Ver resultados"
    view._go_next()
    assert finished == [session] and session.correct_count == 1


def test_stale_code_only_allows_skipping(qapp: QApplication) -> None:
    view = _view("// otra cosa\nvoid m() {}")
    session = _session()
    view.start(session, None)
    view.select_line(20)
    assert view.selected_line is None and not view._check.isEnabled()
    view._skip()
    assert session.results[-1].outcome is Outcome.SKIPPED and not view._feedback._change.isVisibleTo(view)
