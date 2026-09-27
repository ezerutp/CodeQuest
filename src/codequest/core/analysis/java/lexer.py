"""Tokenizador por líneas para el resaltado de sintaxis (Java y, con otras palabras clave, TypeScript).

Trabaja línea a línea porque así lo pide QSyntaxHighlighter: cada línea recibe el
estado con el que terminó la anterior (dentro de un comentario de bloque o de un
text block) y devuelve el suyo. No depende de Qt.
"""

import re
from dataclasses import dataclass
from enum import IntEnum, StrEnum

KEYWORDS = frozenset("""
    abstract assert boolean break byte case catch char class const continue default do double
    else enum extends final finally float for goto if implements import instanceof int interface
    long native new package private protected public return short static strictfp super switch
    synchronized this throw throws transient try void volatile while var record sealed permits
    non-sealed yield true false null
""".split())

# Sin get/set: son contextuales y en React aparecen sobre todo como métodos (params.get(…)).
TS_KEYWORDS = frozenset("""
    abstract any as async await boolean break case catch class const continue debugger declare default
    delete do else enum export extends false finally for from function if implements import in
    infer instanceof interface keyof let namespace never new null number object of private protected
    public readonly return satisfies static string super switch symbol this throw true try type
    typeof undefined unknown var void while yield
""".split())
_TS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")


def keywords_for(file: str | None) -> frozenset[str]:
    """Palabras clave según la extensión del archivo; Java por defecto."""
    return TS_KEYWORDS if file and file.endswith(_TS_SUFFIXES) else KEYWORDS


class TokenKind(StrEnum):
    KEYWORD = "keyword"
    TYPE = "type"
    STRING = "string"
    NUMBER = "number"
    COMMENT = "comment"
    ANNOTATION = "annotation"


class LineState(IntEnum):
    NORMAL = 0
    BLOCK_COMMENT = 1
    TEXT_BLOCK = 2
    TEMPLATE = 3  # template string de TypeScript: `...` puede ocupar varias líneas


@dataclass(frozen=True, slots=True)
class Token:
    start: int
    length: int
    kind: TokenKind


_TOKEN = re.compile(
    r"(?P<line_comment>//.*)"
    r"|(?P<block_comment>/\*)"
    r'|(?P<text_block>""")'
    r"|(?P<template>`)"
    r'|(?P<string>"(?:\\.|[^"\\])*"?)'
    r"|(?P<char>'(?:\\.|[^'\\])*'?)"
    r"|(?P<annotation>@\s*[A-Za-z_][\w.]*)"
    r"|(?P<number>\b(?:0[xX][\da-fA-F_]+|0[bB][01_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?)[lLfFdD]?\b)"
    r"|(?P<word>[A-Za-z_$][\w$]*(?:-sealed)?)"
)
_CLOSERS = {LineState.BLOCK_COMMENT: ("*/", TokenKind.COMMENT), LineState.TEXT_BLOCK: ('"""', TokenKind.STRING),
            LineState.TEMPLATE: ("`", TokenKind.STRING)}
_OPENERS = {"block_comment": LineState.BLOCK_COMMENT, "text_block": LineState.TEXT_BLOCK,
            "template": LineState.TEMPLATE}


def tokenize_line(line: str, state: LineState = LineState.NORMAL,
                  keywords: frozenset[str] = KEYWORDS) -> tuple[list[Token], LineState]:
    tokens: list[Token] = []
    pos = 0

    if state is not LineState.NORMAL:
        closer, kind = _CLOSERS[state]
        end = line.find(closer)
        if end == -1:
            return [Token(0, len(line), kind)] if line else [], state
        pos = end + len(closer)
        tokens.append(Token(0, pos, kind))
        state = LineState.NORMAL

    while (match := _TOKEN.search(line, pos)) is not None:
        group, start = match.lastgroup, match.start()
        pos = match.end()
        if group in _OPENERS:
            new_state = _OPENERS[group]
            closer, kind = _CLOSERS[new_state]
            end = line.find(closer, pos)
            if end == -1:
                tokens.append(Token(start, len(line) - start, kind))
                return tokens, new_state
            pos = end + len(closer)
            tokens.append(Token(start, pos - start, kind))
        elif group == "line_comment":
            tokens.append(Token(start, pos - start, TokenKind.COMMENT))
        elif group in ("string", "char"):
            tokens.append(Token(start, pos - start, TokenKind.STRING))
        elif group == "annotation":
            kind = TokenKind.KEYWORD if match.group() == "@interface" else TokenKind.ANNOTATION
            tokens.append(Token(start, pos - start, kind))
        elif group == "number":
            tokens.append(Token(start, pos - start, TokenKind.NUMBER))
        elif group == "word":
            word = match.group()
            if word in keywords:
                tokens.append(Token(start, pos - start, TokenKind.KEYWORD))
            elif word[0].isupper():
                tokens.append(Token(start, pos - start, TokenKind.TYPE))
    return tokens, LineState.NORMAL
