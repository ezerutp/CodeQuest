"""Modo "Corrige el código": el estudiante edita el fragmento con el error hasta arreglarlo.

La evaluación es local. La versión del estudiante se coloca en su archivo, en memoria, para
comprobar la sintaxis en contexto con tree-sitter, y después se compara con el código original
token a token (los espacios y comentarios no cuentan). Nunca se escribe en el proyecto.
"""

from dataclasses import dataclass
from enum import StrEnum

from codequest.core.analysis.java.syntax import syntax_error_lines, tokens, tokens_by_line
from codequest.core.games.base import BaseGameMode, Evaluation, Outcome
from codequest.core.games.catalog import FIX_CODE
from codequest.core.questions.models import Question


@dataclass(frozen=True, slots=True)
class CodeFix:
    """Respuesta del estudiante y lo necesario para evaluarla."""

    edited: str  # su versión del fragmento
    original: str  # el fragmento real, sin el error
    first_line: int  # línea real donde empieza el fragmento
    file_text: str | None = None  # archivo completo, para comprobar la sintaxis en contexto


class FixKind(StrEnum):
    FIXED = "fixed"  # igual que el original: correcto
    OTHER_CHANGES = "other_changes"  # arregló el error pero cambió otras cosas
    SYNTAX_ERROR = "syntax_error"
    UNCHANGED = "unchanged"  # no tocó nada
    STILL_BROKEN = "still_broken"  # cambió algo, pero la línea del error sigue mal


@dataclass(frozen=True, slots=True)
class FixResult:
    kind: FixKind
    error_line: int | None = None  # línea real del primer error de sintaxis


_OUTCOMES = {
    FixKind.FIXED: Outcome.CORRECT,
    FixKind.OTHER_CHANGES: Outcome.PARTIAL,
    FixKind.SYNTAX_ERROR: Outcome.INCORRECT,
    FixKind.UNCHANGED: Outcome.INCORRECT,
    FixKind.STILL_BROKEN: Outcome.INCORRECT,
}


def check_fix(question: Question, fix: CodeFix) -> FixResult:
    mutation = question.mutation
    if mutation is None:
        raise ValueError(f"La pregunta {question.key} no tiene un error que corregir")
    edited_tokens = tokens(fix.edited)
    if edited_tokens == tokens(fix.original):
        return FixResult(FixKind.FIXED)
    if edited_tokens == tokens(mutation.apply(fix.original, fix.first_line)):
        return FixResult(FixKind.UNCHANGED)
    if (error := _syntax_error(fix)) is not None:
        return FixResult(FixKind.SYNTAX_ERROR, None if error is True else error)
    fixed_line = tokens_by_line(fix.original).get(mutation.line - fix.first_line)
    if fixed_line in tokens_by_line(fix.edited).values():
        return FixResult(FixKind.OTHER_CHANGES)
    return FixResult(FixKind.STILL_BROKEN)


def _syntax_error(fix: CodeFix) -> int | None | bool:
    """¿La versión del estudiante rompe la sintaxis? Devuelve la línea real del primer error dentro de
    lo editado, True si el error aparece fuera (p. ej. falta un `}` y se nota al final del archivo) o
    None si no hay errores nuevos. Los errores que ya existían no cuentan: un fragmento suelto (una
    cabecera sin su `}`) o un archivo que ya no compilaba no son culpa del estudiante."""
    context = fix.file_text if fix.file_text is not None else fix.original
    offset = fix.first_line - 1 if fix.file_text is not None else 0
    lines = context.split("\n")
    original_count = fix.original.count("\n") + 1
    edited_count = fix.edited.count("\n") + 1
    rebuilt = "\n".join([*lines[:offset], fix.edited, *lines[offset + original_count:]])

    first, last_edited = offset + 1, offset + edited_count
    shift = edited_count - original_count
    # Errores previos, con las líneas posteriores a lo editado desplazadas como en la nueva versión.
    before = {line if line <= offset + original_count else line + shift for line in syntax_error_lines(context)}
    new = [line for line in syntax_error_lines(rebuilt) if line not in before]
    if not new:
        return None
    inside = [line for line in new if first <= line <= last_edited]
    if not inside:
        return True
    return inside[0] - offset + fix.first_line - 1


class FixCodeMode(BaseGameMode):
    mode_id = FIX_CODE

    def evaluate(self, question: Question, answer: CodeFix) -> Evaluation:
        result = check_fix(question, answer)
        return Evaluation(question, _OUTCOMES[result.kind], result)
