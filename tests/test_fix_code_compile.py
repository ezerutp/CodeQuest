"""«Probar» con los errores de compilación de jdtls (función de diagnóstico falsa, sin jdtls)."""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from codequest.core.lsp.models import Diagnostic  # noqa: E402
from test_fix_code_view import CODE, _session, _view  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _diagnose(calls: list[str]):
    """Como jdtls: «FOO» no existe y la mutación (@PostMapping) deja un error propio."""
    def diagnose(path: str, text: str) -> tuple[Diagnostic, ...]:
        calls.append(text)
        errors = []
        for number, line in enumerate(text.split("\n"), start=1):
            if "FOO" in line:
                errors.append(Diagnostic(number, "FOO cannot be resolved"))
            if "@PostMapping" in line:
                errors.append(Diagnostic(number, "error que ya trae el ejercicio"))
        return tuple(errors)
    return diagnose


def _ready_view(calls: list[str]):
    view = _view()
    view._diagnose = _diagnose(calls)
    view.start(_session(), None)
    view.set_language_server_ready(True)
    return view


def _wait(qapp: QApplication, condition, seconds: float = 5) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)


def test_baseline_is_computed_when_the_exercise_opens(qapp: QApplication) -> None:
    calls: list[str] = []
    view = _ready_view(calls)
    _wait(qapp, lambda: view._baseline is not None)
    assert [d.message for d in view._baseline] == ["error que ya trae el ejercicio"]
    assert "@PostMapping" in calls[0]  # la versión con el error, dentro de su archivo
    view.shutdown()


def test_new_compile_errors_replace_the_local_message(qapp: QApplication) -> None:
    calls: list[str] = []
    view = _ready_view(calls)
    view.set_edited_code(CODE.replace("@GetMapping", "@PutMapping").replace("find(id)", "FOO(id)"))
    view._try()
    assert view._compile_note.text() == "Revisando con el compilador…"
    _wait(qapp, lambda: view._trial_text.property("tone") == "danger")
    assert view._trial_text.text() == "Error de compilación en la línea 4: «FOO cannot be resolved»."
    assert view._compile_note.text() == "Lo dice el compilador de Java (jdtls)."
    assert not view._session.is_answered
    view.shutdown()


def test_errors_already_in_the_exercise_are_not_shown(qapp: QApplication) -> None:
    calls: list[str] = []
    view = _ready_view(calls)
    view.set_edited_code(CODE.replace("@GetMapping", "@PostMapping").replace("find(id)", "find(id + 0)"))
    view._try()
    _wait(qapp, lambda: view._compile_note.text() != "Revisando con el compilador…")
    assert view._compile_note.text() == "El compilador no encontró errores nuevos."
    assert view._trial_text.text() == "La sintaxis es correcta, pero el error sigue ahí."
    view.shutdown()


def test_late_results_are_discarded_and_simple_cases_skip_the_compiler(qapp: QApplication) -> None:
    calls: list[str] = []
    view = _ready_view(calls)
    _wait(qapp, lambda: view._baseline is not None)
    view.set_edited_code(CODE.replace("@GetMapping", "@PutMapping").replace("find(id)", "FOO(id)"))
    view._try()
    view.set_edited_code(CODE)  # sigue escribiendo antes de que responda el compilador
    _wait(qapp, lambda: len(calls) >= 2)
    for _ in range(20):
        qapp.processEvents()
        time.sleep(0.005)
    assert not view._trial.isVisibleTo(view)
    count = len(calls)
    view._try()  # igual que el original: no hace falta el compilador
    assert view._trial_text.property("tone") == "success" and len(calls) == count
    assert not view._compile_note.isVisibleTo(view)
    view.shutdown()


def test_without_language_server_probar_stays_local(qapp: QApplication) -> None:
    calls: list[str] = []
    view = _view()
    view._diagnose = _diagnose(calls)
    view.start(_session(), None)
    view.set_edited_code(CODE.replace("@GetMapping", "@PutMapping"))
    view._try()
    assert calls == [] and not view._compile_note.isVisibleTo(view)
    view.shutdown()
