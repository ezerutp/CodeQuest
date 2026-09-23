from codequest.core.analysis.java.lexer import LineState, TokenKind, tokenize_line


def kinds(line: str, state: LineState = LineState.NORMAL) -> list[tuple[str, TokenKind]]:
    tokens, _ = tokenize_line(line, state)
    return [(line[t.start:t.start + t.length], t.kind) for t in tokens]


def test_keywords_types_annotations_and_strings() -> None:
    assert kinds('@GetMapping("/{id}") public ResponseEntity<User> get(@PathVariable Long id) {') == [
        ("@GetMapping", TokenKind.ANNOTATION),
        ('"/{id}"', TokenKind.STRING),
        ("public", TokenKind.KEYWORD),
        ("ResponseEntity", TokenKind.TYPE),
        ("User", TokenKind.TYPE),
        ("@PathVariable", TokenKind.ANNOTATION),
        ("Long", TokenKind.TYPE),
    ]


def test_numbers_chars_and_literals() -> None:
    assert kinds("long x = 0xFF + 1_000L + 3.5e2; char c = '\\''; boolean b = null == true;") == [
        ("long", TokenKind.KEYWORD),
        ("0xFF", TokenKind.NUMBER),
        ("1_000L", TokenKind.NUMBER),
        ("3.5e2", TokenKind.NUMBER),
        ("char", TokenKind.KEYWORD),
        ("'\\''", TokenKind.STRING),
        ("boolean", TokenKind.KEYWORD),
        ("null", TokenKind.KEYWORD),
        ("true", TokenKind.KEYWORD),
    ]


def test_keywords_inside_strings_and_comments_are_not_highlighted() -> None:
    assert kinds('String s = "public class"; // return new X') == [
        ("String", TokenKind.TYPE),
        ('"public class"', TokenKind.STRING),
        ("// return new X", TokenKind.COMMENT),
    ]


def test_identifiers_with_digits_are_not_numbers() -> None:
    assert kinds("int user1 = v2;") == [("int", TokenKind.KEYWORD)]


def test_block_comment_spanning_lines() -> None:
    tokens, state = tokenize_line("int a; /* inicio")
    assert state is LineState.BLOCK_COMMENT
    assert tokens[-1].kind is TokenKind.COMMENT

    assert kinds("   sigue public", LineState.BLOCK_COMMENT) == [("   sigue public", TokenKind.COMMENT)]
    assert tokenize_line("   sigue", LineState.BLOCK_COMMENT)[1] is LineState.BLOCK_COMMENT

    tokens, state = tokenize_line("fin */ return;", LineState.BLOCK_COMMENT)
    assert state is LineState.NORMAL
    assert kinds("fin */ return;", LineState.BLOCK_COMMENT) == [
        ("fin */", TokenKind.COMMENT), ("return", TokenKind.KEYWORD),
    ]


def test_text_block_spanning_lines() -> None:
    _, state = tokenize_line('String q = """')
    assert state is LineState.TEXT_BLOCK
    assert kinds("  SELECT * FROM users", state) == [("  SELECT * FROM users", TokenKind.STRING)]
    assert tokenize_line('  """;', state)[1] is LineState.NORMAL


def test_annotation_type_declaration() -> None:
    assert kinds("public @interface Audited {") == [
        ("public", TokenKind.KEYWORD), ("@interface", TokenKind.KEYWORD), ("Audited", TokenKind.TYPE),
    ]


def test_empty_line_keeps_state() -> None:
    assert tokenize_line("", LineState.BLOCK_COMMENT) == ([], LineState.BLOCK_COMMENT)
