import random
from pathlib import Path

import pytest

from codequest.core.analysis.java.syntax import syntax_error_lines, tokens, tokens_by_line
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.snippets import SnippetRef
from codequest.core.games.base import Outcome
from codequest.core.games.catalog import FIX_CODE, mode_info
from codequest.core.games.fix_code import CodeFix, FixCodeMode, FixKind, check_fix
from codequest.core.questions.models import Question
from codequest.services.learning_service import LearningService
from codequest.services.project_service import ProjectService

SHOP = Path(__file__).parent / "fixtures" / "shop"


@pytest.fixture(scope="module")
def service() -> ProjectService:
    return ProjectService()


@pytest.fixture(scope="module")
def model(service: ProjectService) -> ProjectModel:
    return service.analyze(service.detect(SHOP))


def _question(model: ProjectModel, suffix: str) -> Question:
    session = LearningService(rng=random.Random(0)).start_session(model, FIX_CODE, size=100)
    return next(q for q in session.questions if q.key.endswith(suffix))


def _fix(service: ProjectService, model: ProjectModel, question: Question):
    """(original, versión con el error, función que evalúa una edición)."""
    snippet = service.read_snippet(model, question.snippet)
    file_text = service.read_snippet(model, SnippetRef.whole_file(question.snippet.file)).text
    mutated = question.mutation.apply(snippet.text, snippet.start_line)

    def check(edited: str, with_file: bool = True):
        return check_fix(question, CodeFix(edited, snippet.text, snippet.start_line, file_text if with_file else None))

    return snippet.text, mutated, check


# --- tokens y sintaxis -------------------------------------------------------------------

def test_tokens_ignore_spacing_and_comments() -> None:
    assert tokens("int  x =1; // hola") == tokens("int x = 1; /* otra */")
    assert tokens('String s = "a  b";') != tokens('String s = "a b";')  # dentro de un string sí cuenta
    assert tokens_by_line("a();\n\n  b();") == {0: ("a", "(", ")", ";"), 2: ("b", "(", ")", ";")}


def test_syntax_errors_by_line() -> None:
    assert syntax_error_lines("class A {\n  void m() { int x = ; }\n}") == [2]
    assert syntax_error_lines("class A { void m() {} }") == []


# --- evaluación ----------------------------------------------------------------------------

def test_mode_is_local_and_registered(model: ProjectModel) -> None:
    info = mode_info(FIX_CODE)
    assert info.available and not info.uses_ai
    session = LearningService(rng=random.Random(1)).start_session(model, FIX_CODE)
    assert 0 < session.total <= 5
    assert all(q.key.startswith("fix:") and q.mutation is not None for q in session.questions)


def test_restoring_the_line_is_correct_even_with_other_formatting(service: ProjectService,
                                                                  model: ProjectModel) -> None:
    question = _question(model, "UserController#getUser():id")
    original, _, check = _fix(service, model, question)
    assert check(original).kind is FixKind.FIXED
    reformatted = original.replace("(@PathVariable Long id) {", "( @PathVariable  Long id ) { // arreglado")
    assert check(reformatted).kind is FixKind.FIXED
    evaluation = FixCodeMode().evaluate(question, CodeFix(original, original, question.snippet.start_line))
    assert evaluation.outcome is Outcome.CORRECT and evaluation.answer.kind is FixKind.FIXED


def test_untouched_or_still_broken_code_is_incorrect(service: ProjectService, model: ProjectModel) -> None:
    question = _question(model, "UserController#getUser():id")
    _, mutated, check = _fix(service, model, question)
    assert check(mutated).kind is FixKind.UNCHANGED
    assert check(mutated.replace("@RequestBody", "@RequestParam")).kind is FixKind.STILL_BROKEN


def test_syntax_errors_point_to_the_student_line(service: ProjectService, model: ProjectModel) -> None:
    question = _question(model, "UserServiceImpl#findById():userRepository.findById")
    original, _, check = _fix(service, model, question)
    first = question.snippet.start_line
    lines = original.split("\n")
    index = next(i for i, line in enumerate(lines) if "orElseThrow" in line)
    lines[index] = lines[index].replace(";", "")
    result = check("\n".join(lines))
    assert result.kind is FixKind.SYNTAX_ERROR and first + index <= result.error_line <= first + index + 1
    # Una llave sin cerrar se nota al final del archivo: sigue siendo un error de sintaxis.
    assert check(original + " {").kind is FixKind.SYNTAX_ERROR


def test_fixing_the_error_but_changing_more_is_partial(service: ProjectService, model: ProjectModel) -> None:
    question = _question(model, "UserController#getUser():id")
    original, _, check = _fix(service, model, question)
    evaluation = FixCodeMode().evaluate(question, CodeFix(original.replace("findById(id)", "findById(1L)"),
                                                          original, question.snippet.start_line))
    assert evaluation.outcome is Outcome.PARTIAL and evaluation.answer.kind is FixKind.OTHER_CHANGES


def test_existing_errors_of_a_loose_fragment_do_not_count(service: ProjectService, model: ProjectModel) -> None:
    question = _question(model, "Order#")  # cabecera de clase: el fragmento no cierra su `}`
    original, _, check = _fix(service, model, question)
    assert syntax_error_lines(original)  # suelto, "falla"...
    assert check(original, with_file=False).kind is FixKind.FIXED  # ...pero no por culpa del estudiante


def test_checking_fixes_never_touches_the_project(service: ProjectService, model: ProjectModel) -> None:
    import hashlib

    def digest() -> dict[Path, str]:
        return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in SHOP.rglob("*") if p.is_file()}

    before = digest()
    for question in LearningService(rng=random.Random(0)).start_session(model, FIX_CODE, size=100).questions:
        original, mutated, check = _fix(service, model, question)
        check(original), check(mutated), check(original + " {")
    assert digest() == before
