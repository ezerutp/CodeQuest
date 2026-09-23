from codequest.core.analysis.java.source_text import LineIndex, mask_source, normalize_type


def test_mask_preserves_length_and_lines() -> None:
    text = 'a /* x\n y */ b // c {\n"s { ; }" \'{\' """\nblock {\n"""'
    masked = mask_source(text)

    assert len(masked) == len(text)
    assert masked.count("\n") == text.count("\n")
    assert "{" not in masked and ";" not in masked
    assert masked.startswith("a ") and "b" in masked


def test_mask_handles_escaped_quotes() -> None:
    masked = mask_source(r'x = "a \" { b"; y = 1;')
    assert "{" not in masked
    assert masked.endswith("y = 1;")


def test_line_index() -> None:
    lines = LineIndex("a\nbc\nd")
    assert [lines.line_of(i) for i in (0, 1, 2, 3, 4, 5)] == [1, 1, 2, 2, 2, 3]


def test_normalize_type() -> None:
    assert normalize_type("Map< String ,\n  List<X> >") == "Map<String, List<X>>"
    assert normalize_type("int [ ]") == "int[]"
