from codequest.core.lsp.documents import splice, utf16_column

FILE = "class A {\n    void a() {\n        x();\n    }\n}\n"


def test_splice_replaces_the_snippet_lines_even_with_more_lines() -> None:
    original = "    void a() {\n        x();\n    }"
    edited = "    void a() {\n        x();\n        y.\n    }"
    assert splice(FILE, 2, original, edited) == "class A {\n" + edited + "\n}\n"
    assert splice(FILE, 2, original, original) == FILE


def test_utf16_column_counts_surrogate_pairs() -> None:
    assert utf16_column("abc.", 4) == 4
    assert utf16_column('"😀".', 4) == 5
