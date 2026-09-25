from codequest.core.lsp.documents import new_errors, splice, utf16_column

FILE = "class A {\n    void a() {\n        x();\n    }\n}\n"


def test_splice_replaces_the_snippet_lines_even_with_more_lines() -> None:
    original = "    void a() {\n        x();\n    }"
    edited = "    void a() {\n        x();\n        y.\n    }"
    assert splice(FILE, 2, original, edited) == "class A {\n" + edited + "\n}\n"
    assert splice(FILE, 2, original, original) == FILE


def test_utf16_column_counts_surrogate_pairs() -> None:
    assert utf16_column("abc.", 4) == 4
    assert utf16_column('"😀".', 4) == 5


def test_new_errors_ignore_known_messages_warnings_and_lines_outside_the_snippet() -> None:
    from codequest.core.lsp.models import Diagnostic

    baseline = [Diagnostic(5, "Type mismatch")]
    current = [Diagnostic(1, "fuera del fragmento"), Diagnostic(6, "Type mismatch"),  # se movió de línea
               Diagnostic(7, "FOO cannot be resolved"), Diagnostic(7, "unused", is_error=False),
               Diagnostic(8, "Type mismatch")]  # uno más que en la versión de partida
    assert [(d.line, d.message) for d in new_errors(current, baseline, 4, 5)] == [
        (7, "FOO cannot be resolved"), (8, "Type mismatch")]
