from pathlib import Path

import pytest

from codequest.core.project.detector import ProjectDetector
from codequest.core.project.models import BuildTool, Framework, Language

SPRING_POM = """<project>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
  </parent>
</project>"""


def _write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def detector() -> ProjectDetector:
    return ProjectDetector()


def test_detects_spring_boot_maven_project(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "pom.xml", SPRING_POM)
    _write(tmp_path / "src/main/java/com/example/App.java", "class App {}")

    info = detector.detect(tmp_path)

    assert info.language is Language.JAVA
    assert info.framework is Framework.SPRING_BOOT
    assert info.build_tool is BuildTool.MAVEN
    assert info.stack == ("Spring Boot", "Java", "Maven")
    assert info.is_supported
    assert info.warnings == ()


def test_detects_spring_boot_gradle_kts_project(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "build.gradle.kts", 'plugins { id("org.springframework.boot") version "3.3.0" }')
    _write(tmp_path / "src/main/java/App.java", "class App {}")

    info = detector.detect(tmp_path)

    assert info.build_tool is BuildTool.GRADLE
    assert info.framework is Framework.SPRING_BOOT


def test_plain_java_project_without_spring(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "pom.xml", "<project><artifactId>demo</artifactId></project>")
    _write(tmp_path / "src/main/java/App.java", "class App {}")

    info = detector.detect(tmp_path)

    assert info.language is Language.JAVA
    assert info.framework is Framework.NONE


def test_java_sources_outside_standard_layout(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "module-a/src/Foo.java", "class Foo {}")

    assert detector.detect(tmp_path).language is Language.JAVA


def test_ignores_java_files_in_build_output(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "target/generated/Foo.java", "class Foo {}")
    _write(tmp_path / "node_modules/pkg/Bar.java", "class Bar {}")

    assert detector.detect(tmp_path).language is Language.UNKNOWN


def test_empty_directory_is_not_a_code_project(tmp_path: Path, detector: ProjectDetector) -> None:
    info = detector.detect(tmp_path)

    assert not info.is_code_project
    assert not info.is_supported
    assert info.warnings


def test_reads_git_remote_without_credentials(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / ".git/config",
           '[core]\n\tbare = false\n[remote "origin"]\n\turl = https://user:ghp_secret@github.com/me/app.git\n')

    info = detector.detect(tmp_path)

    assert info.git_remote == "https://github.com/me/app.git"


def test_rejects_non_directory(tmp_path: Path, detector: ProjectDetector) -> None:
    with pytest.raises(NotADirectoryError):
        detector.detect(tmp_path / "missing")


def test_never_writes_inside_project(tmp_path: Path, detector: ProjectDetector) -> None:
    _write(tmp_path / "pom.xml", SPRING_POM)
    _write(tmp_path / "src/main/java/App.java", "class App {}")
    before = sorted((p, p.stat().st_mtime_ns) for p in tmp_path.rglob("*"))

    detector.detect(tmp_path)

    assert sorted((p, p.stat().st_mtime_ns) for p in tmp_path.rglob("*")) == before
