"""Tests para el parser TypeScript/TSX y el ReactAnalyzer."""

from pathlib import Path

import pytest

from codequest.core.analysis.react.analyzer import ReactAnalyzer
from codequest.core.analysis.react.roles import ReactRole
from codequest.core.analysis.typescript.models import TSClass, TSTypeKind
from codequest.core.analysis.typescript.parser import TreeSitterTypeScriptParser
from codequest.core.project.models import BuildTool, Framework, Language, ProjectInfo, SourceFile


@pytest.fixture
def parser() -> TreeSitterTypeScriptParser:
    return TreeSitterTypeScriptParser()


@pytest.fixture
def react_info(tmp_path: Path) -> ProjectInfo:
    return ProjectInfo(
        root=tmp_path,
        name="frontend",
        markers=("package.json",),
        language=Language.TYPESCRIPT,
        framework=Framework.REACT,
        build_tool=BuildTool.NONE,
    )


def _source_file(tmp_path: Path, name: str, content: str) -> SourceFile:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return SourceFile(path=path, relative_path=name, size=len(content))


def _ts_class(name: str, kind: TSTypeKind, **kwargs) -> TSClass:
    return TSClass(
        name=name,
        kind=kind,
        file="test.ts",
        is_test=False,
        start_line=1,
        end_line=1,
        **kwargs,
    )


# ── Parser TypeScript ────────────────────────────────────────────────────────


def test_parses_interface(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "types.ts", """
export interface User {
  id: number;
  name: string;
}
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    cls = classes[0]
    assert cls.name == "User"
    assert cls.kind is TSTypeKind.INTERFACE
    assert len(cls.fields) == 2
    assert cls.fields[0].name == "id"
    assert cls.fields[0].type == "number"


def test_parses_type_alias(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "types.ts", """
export type Status = 'idle' | 'loading' | 'error';
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    assert classes[0].name == "Status"
    assert classes[0].kind is TSTypeKind.TYPE_ALIAS


def test_parses_class(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "service.ts", """
export class UserService {
  private api: string;

  constructor(api: string) {
    this.api = api;
  }

  async getUser(id: number): Promise<string> {
    return 'name';
  }
}
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    cls = classes[0]
    assert cls.name == "UserService"
    assert cls.kind is TSTypeKind.CLASS
    assert len(cls.methods) == 2
    assert cls.methods[0].name == "constructor"
    assert cls.methods[1].name == "getUser"


def test_parses_enum(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "enums.ts", """
export enum Color {
  Red = 'red',
  Green = 'green',
}
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    assert classes[0].name == "Color"
    assert classes[0].kind is TSTypeKind.ENUM


def test_parses_export_default_function(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "helper.ts", """
export default function formatName(first: string, last: string): string {
  return `${first} ${last}`;
}
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    cls = classes[0]
    assert cls.name == "formatName"
    assert cls.kind is TSTypeKind.FUNCTION
    assert len(cls.methods) == 1
    assert cls.methods[0].return_type == "string"


def test_parameter_names_including_destructuring(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "Card.tsx", """
export function Card({ title, size = 1, style: { color }, ...rest }: Props, [first, , second = 2]: Pair,
                     id?: number, ...tags: string[]) {
  return <div>{title}</div>;
}
""")
    (cls,) = parser.parse(sf, sf.read_text())
    assert cls.methods[0].parameters == (
        "{ title, size, style, ...rest }: Props",
        "[first, second]: Pair",
        "id?: number",
        "...tags: string[]",
    )


def test_detects_react_component(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "App.tsx", """
export default function App() {
  return <div>Hello</div>;
}
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    assert classes[0].is_component
    assert not classes[0].is_hook


def test_detects_react_hook(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "useCounter.ts", """
import { useState } from 'react';

export function useCounter() {
  const [count, setCount] = useState(0);
  return { count, setCount };
}
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    assert classes[0].is_hook
    assert not classes[0].is_component


def test_detects_hook_with_use_effect(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "useData.ts", """
import { useEffect, useState } from 'react';

export function useData() {
  const [data, setData] = useState(null);
  useEffect(() => { fetch('/api').then(r => r.json()).then(setData); }, []);
  return data;
}
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    assert classes[0].is_hook


def test_detects_usual_react_component_shapes(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "shapes.tsx", """
import React, { memo, useState } from 'react';
export function Card() {
  return (
    <div>hi</div>
  );
}
export function Counter() { const [n] = useState(0); return <b>{n}</b>; }
export const Header = () => <h1>t</h1>;
const Maybe = ({ ok }: Props) => ok ? <p /> : null;
export const Item = memo(({ id }: P) => <li>{id}</li>);
export const Input = React.forwardRef(function Input(props, ref) { return <input ref={ref} />; });
const useToggle = (initial = false) => { const [v, s] = useState(initial); return [v, () => s(!v)]; };
export const sum = (a: number, b: number) => a + b;
export const API_URL = '/api';
const data = fetchData(() => 1);
function Etiqueta() { const mapa = useMap(); useEffect(() => {}, [mapa]); return null; }
""")
    by_name = {c.name: c for c in parser.parse(sf, sf.read_text())}

    assert set(by_name) == {"Card", "Counter", "Header", "Maybe", "Item", "Input", "useToggle", "sum", "Etiqueta"}
    components = {n for n, c in by_name.items() if c.is_component}
    assert components == {"Card", "Counter", "Header", "Maybe", "Item", "Input", "Etiqueta"}  # null + hooks
    assert {n for n, c in by_name.items() if c.is_hook} == {"useToggle"}  # Counter usa hooks pero es componente
    assert by_name["Card"].modifiers == ("export",)
    assert by_name["Item"].methods[0].parameters == ("{ id }: P",)
    assert (by_name["Card"].start_line, by_name["Card"].end_line) == (3, 7)


def test_plain_function_is_neither_component_nor_hook(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "utils.ts", """
export function add(a: number, b: number): number {
  return a + b;
}
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    assert not classes[0].is_component
    assert not classes[0].is_hook


def test_supports_ts_and_tsx(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf_ts = _source_file(tmp_path, "a.ts", "export const x: number = 1;")
    sf_tsx = _source_file(tmp_path, "b.tsx", "export const x = <div/>;")
    sf_js = _source_file(tmp_path, "c.js", "const x = 1;")
    assert parser.supports(sf_ts)
    assert parser.supports(sf_tsx)
    assert not parser.supports(sf_js)


def test_parses_tsx_with_jsx_elements(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "Component.tsx", """
export function Button({ label }: { label: string }) {
  return <button>{label}</button>;
}
""")
    classes = parser.parse(sf, sf.read_text())
    assert len(classes) == 1
    assert classes[0].is_component
    assert classes[0].kind is TSTypeKind.FUNCTION


def test_tolerates_broken_code(parser: TreeSitterTypeScriptParser, tmp_path: Path) -> None:
    sf = _source_file(tmp_path, "broken.ts", """
export function foo(: {
  return <div>
""")
    classes = parser.parse(sf, sf.read_text())
    assert isinstance(classes, list)


# ── ReactAnalyzer ─────────────────────────────────────────────────────────────


def test_supports_react_project(react_info: ProjectInfo) -> None:
    analyzer = ReactAnalyzer()
    assert analyzer.supports(react_info)


def test_does_not_support_java_project(tmp_path: Path) -> None:
    java_info = ProjectInfo(
        root=tmp_path, name="backend", markers=("pom.xml",),
        language=Language.JAVA, framework=Framework.SPRING_BOOT, build_tool=BuildTool.MAVEN,
    )
    analyzer = ReactAnalyzer()
    assert not analyzer.supports(java_info)


def test_classifies_component(react_info: ProjectInfo) -> None:
    analyzer = ReactAnalyzer()
    component = _ts_class("App", TSTypeKind.FUNCTION, is_component=True)
    roles = analyzer.classify([component])
    assert roles["App"] is ReactRole.COMPONENT


def test_classifies_hook(react_info: ProjectInfo) -> None:
    analyzer = ReactAnalyzer()
    hook = _ts_class("useCounter", TSTypeKind.FUNCTION, is_hook=True)
    roles = analyzer.classify([hook])
    assert roles["useCounter"] is ReactRole.HOOK


def test_classifies_interface_as_type(react_info: ProjectInfo) -> None:
    analyzer = ReactAnalyzer()
    iface = _ts_class("User", TSTypeKind.INTERFACE)
    roles = analyzer.classify([iface])
    assert roles["User"] is ReactRole.TYPE


def test_classifies_type_alias_as_type(react_info: ProjectInfo) -> None:
    analyzer = ReactAnalyzer()
    alias = _ts_class("Status", TSTypeKind.TYPE_ALIAS)
    roles = analyzer.classify([alias])
    assert roles["Status"] is ReactRole.TYPE


def test_classifies_enum(react_info: ProjectInfo) -> None:
    analyzer = ReactAnalyzer()
    enum = _ts_class("Color", TSTypeKind.ENUM)
    roles = analyzer.classify([enum])
    assert roles["Color"] is ReactRole.ENUM


def test_component_using_hooks_is_a_component(react_info: ProjectInfo) -> None:
    app = _ts_class("App", TSTypeKind.FUNCTION, is_component=True, is_hook=True)
    assert ReactAnalyzer().classify([app])["App"] is ReactRole.COMPONENT


def test_classifies_plain_function_as_utility(react_info: ProjectInfo) -> None:
    analyzer = ReactAnalyzer()
    func = _ts_class("add", TSTypeKind.FUNCTION)
    roles = analyzer.classify([func])
    assert roles["add"] is ReactRole.UTILITY


def test_classifies_class_as_service(react_info: ProjectInfo) -> None:
    analyzer = ReactAnalyzer()
    svc = _ts_class("UserService", TSTypeKind.CLASS)
    roles = analyzer.classify([svc])
    assert roles["UserService"] is ReactRole.SERVICE
