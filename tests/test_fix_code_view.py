"""Flujo de "Corrige el código" con un QApplication offscreen."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from codequest.core.analysis.snippets import CodeSnippet, SnippetRef  # noqa: E402
from codequest.core.games.base import GameSession, Outcome  # noqa: E402
from codequest.core.games.fix_code import FixCodeMode, FixKind  # noqa: E402
from codequest.core.knowledge.base import KnowledgeBase  # noqa: E402
from codequest.core.questions.models import CodeMutation, Question  # noqa: E402
from codequest.ui.pages.learn.fix_code_view import FixCodeView  # noqa: E402

HEADER = "class UserController {\n"
CODE = '    @GetMapping("/{id}")\n    public User get(@PathVariable Long id) {\n        return service.find(id);\n    }'
FILE = HEADER + CODE + "\n}\n"


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _session() -> GameSession:
    concept = KnowledgeBase.default().for_annotation("GetMapping")
    mutation = CodeMutation(line=2, column=4, end_column=15, original="@GetMapping", replacement="@PostMapping",
                            explanation="`get()` consulta.")
    questions = [Question(key=f"fix:q{i}", prompt="Corrígelo.", concept=concept, class_name="C",
                          snippet=SnippetRef("A.java", 2, 5), mutation=mutation) for i in range(2)]
    return GameSession(FixCodeMode(), questions)


def _view() -> FixCodeView:
    def load(ref: SnippetRef) -> CodeSnippet:
        if ref == SnippetRef.whole_file("A.java"):
            return CodeSnippet(ref.file, 1, FILE.count("\n"), FILE)
        return CodeSnippet(ref.file, ref.start_line, ref.end_line, CODE)

    return FixCodeView(load)


def test_editor_starts_with_the_mutated_copy_and_is_editable(qapp: QApplication) -> None:
    view = _view()
    view.start(_session(), None)
    assert view.edited_code().startswith('    @PostMapping("/{id}")')
    assert not view._editor.isReadOnly() and view._editor.first_line == 2


def test_fixing_the_code_is_correct(qapp: QApplication) -> None:
    view = _view()
    session = _session()
    view.start(session, None)
    evaluations = []
    view.answered.connect(evaluations.append)
    view.set_edited_code(CODE)
    view._answer()
    assert evaluations[0].outcome is Outcome.CORRECT
    assert view._editor.isReadOnly() and view._next.isVisibleTo(view)
    assert "Arreglaste el error de la línea 2" in view._feedback._title.text()
    assert view._feedback._original.text() == '@GetMapping("/{id}")'


def test_syntax_error_is_reported_with_its_real_line(qapp: QApplication) -> None:
    view = _view()
    session = _session()
    view.start(session, None)
    view.set_edited_code(CODE.replace("find(id);", "find(id)"))
    view._answer()
    result = session.results[-1].answer
    assert result.kind is FixKind.SYNTAX_ERROR and result.error_line in (4, 5)
    assert f"línea {result.error_line}" in view._feedback._title.text()


def test_reset_restores_the_exercise_and_round_ends(qapp: QApplication) -> None:
    view = _view()
    session = _session()
    view.start(session, None)
    finished = []
    view.finished.connect(finished.append)
    view.set_edited_code("lo que sea")
    view._restore()
    assert view.edited_code().startswith('    @PostMapping')
    view._confirm()  # comprobar sin cambios
    assert session.results[-1].answer.kind is FixKind.UNCHANGED
    view._confirm()  # siguiente
    view._skip()
    view._go_next()
    assert finished == [session]


def test_ctrl_enter_checks_while_typing_in_the_editor(qapp: QApplication) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    view = _view()
    session = _session()
    view.show()
    view.start(session, None)
    view._editor.setFocus()
    QTest.keyClick(view._editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert session.is_answered and "\n\n" not in view.edited_code()[:30]
    view.hide()
