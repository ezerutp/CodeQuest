"""Tests para detección de React/TypeScript y discovery multi-proyecto."""

import json
from pathlib import Path

import pytest

from codequest.core.project.detector import ProjectDetector
from codequest.core.project.models import BuildTool, Framework, Language


@pytest.fixture
def detector() -> ProjectDetector:
    return ProjectDetector()


def _write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _pkg_json(**deps: str) -> str:
    return json.dumps({"dependencies": deps})


# ── React / TypeScript ────────────────────────────────────────────────────────


def test_detects_react_project(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "package.json", _pkg_json(react="^18.0.0", **{"react-dom": "^18.0.0"}))
    _write(tmp_path / "src/App.tsx", "export default function App() { return null; }")

    info = detector.detect(tmp_path)

    assert info.language is Language.TYPESCRIPT
    assert info.framework is Framework.REACT
    assert info.build_tool is BuildTool.NONE
    assert info.stack == ("React", "TypeScript")
    assert info.is_supported


def test_detects_react_in_dev_dependencies(tmp_path: Path, detector: ProjectDetector) -> None:
    pkg = {"dependencies": {}, "devDependencies": {"react": "^18.0.0"}}
    _write(tmp_path / "package.json", json.dumps(pkg))
    _write(tmp_path / "src/index.ts", "console.log('hi');")

    info = detector.detect(tmp_path)

    assert info.framework is Framework.REACT


def test_typescript_without_react(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "package.json", _pkg_json(express="^4.0.0"))
    _write(tmp_path / "src/server.ts", "const x: number = 1;")

    info = detector.detect(tmp_path)

    assert info.language is Language.TYPESCRIPT
    assert info.framework is Framework.NONE
    assert info.stack == ("TypeScript",)


def test_package_json_without_react_is_not_react(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "package.json", _pkg_json(lodash="^4.0.0"))
    _write(tmp_path / "src/index.ts", "export {};")

    info = detector.detect(tmp_path)

    assert info.framework is Framework.NONE


def test_malformed_package_json_is_not_react(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "package.json", "{invalid json")
    _write(tmp_path / "src/App.tsx", "export default function App() { return null; }")

    info = detector.detect(tmp_path)

    assert info.language is Language.TYPESCRIPT
    assert info.framework is Framework.NONE


def test_ignores_ts_files_in_node_modules(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "node_modules/some-pkg/index.ts", "export {};")

    info = detector.detect(tmp_path)

    assert info.language is Language.UNKNOWN


# ── detect_all: multi-proyecto ───────────────────────────────────────────────


def test_detect_all_finds_backend_and_frontend(tmp_path: Path, detector: ProjectDetector) -> None:
    # Backend Spring Boot
    _write(tmp_path / "backend/pom.xml", '<parent><groupId>org.springframework.boot</groupId></parent>')
    _write(tmp_path / "backend/src/main/java/App.java", "class App {}")
    # Frontend React
    _write(tmp_path / "frontend/package.json", _pkg_json(react="^18.0.0"))
    _write(tmp_path / "frontend/src/App.tsx", "export default function App() { return null; }")

    infos = detector.detect_all(tmp_path)

    assert len(infos) == 2
    names = {i.name for i in infos}
    assert names == {"backend", "frontend"}
    backend = next(i for i in infos if i.name == "backend")
    frontend = next(i for i in infos if i.name == "frontend")
    assert backend.framework is Framework.SPRING_BOOT
    assert backend.language is Language.JAVA
    assert frontend.framework is Framework.REACT
    assert frontend.language is Language.TYPESCRIPT


def test_detect_all_single_project_returns_one(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "pom.xml", "<project><artifactId>demo</artifactId></project>")
    _write(tmp_path / "src/main/java/App.java", "class App {}")

    infos = detector.detect_all(tmp_path)

    assert len(infos) == 1
    assert infos[0].name == tmp_path.name


def test_detect_all_empty_directory_returns_unknown(tmp_path: Path, detector: ProjectDetector) -> None:
    infos = detector.detect_all(tmp_path)

    assert len(infos) == 1
    assert infos[0].language is Language.UNKNOWN
    assert not infos[0].is_code_project


def test_detect_all_ignores_nested_build_dirs(tmp_path: Path, detector: ProjectDetector) -> None:
    # Un solo proyecto con subcarpetas que tienen package.json (p. ej. workspace)
    _write(tmp_path / "package.json", _pkg_json(react="^18.0.0"))
    _write(tmp_path / "src/App.tsx", "export default function App() { return null; }")
    # node_modules tiene package.json pero debe ignorarse
    _write(tmp_path / "node_modules/dep/package.json", _pkg_json(react="^18.0.0"))

    infos = detector.detect_all(tmp_path)

    assert len(infos) == 1
    assert infos[0].name == tmp_path.name


def test_detect_all_respects_max_depth(tmp_path: Path, detector: ProjectDetector) -> None:
    # Subproyecto a profundidad 4 (más allá de _MAX_DISCOVERY_DEPTH=3)
    deep = tmp_path / "a" / "b" / "c" / "d"
    _write(deep / "package.json", _pkg_json(react="^18.0.0"))
    _write(deep / "src/App.tsx", "export default function App() { return null; }")

    infos = detector.detect_all(tmp_path)

    # No debería encontrar el subproyecto profundo: solo devuelve root
    assert len(infos) == 1
    assert infos[0].root == tmp_path


def test_detect_all_rejects_non_directory(tmp_path: Path, detector: ProjectDetector) -> None:
    with pytest.raises(NotADirectoryError):
        detector.detect_all(tmp_path / "missing")


def test_detect_all_never_writes_inside_project(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "backend/pom.xml", "<project><artifactId>api</artifactId></project>")
    _write(tmp_path / "backend/src/main/java/App.java", "class App {}")
    _write(tmp_path / "frontend/package.json", _pkg_json(react="^18.0.0"))
    _write(tmp_path / "frontend/src/App.tsx", "export default function App() { return null; }")
    before = sorted((p, p.stat().st_mtime_ns) for p in tmp_path.rglob("*"))

    detector.detect_all(tmp_path)

    assert sorted((p, p.stat().st_mtime_ns) for p in tmp_path.rglob("*")) == before
