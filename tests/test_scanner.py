from pathlib import Path

from codequest.core.project.scanner import ProjectScanner


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_finds_relevant_files_and_skips_ignored_dirs(tmp_path: Path) -> None:
    _write(tmp_path / "pom.xml")
    _write(tmp_path / "src/main/java/App.java")
    _write(tmp_path / "src/main/resources/application.yml")
    _write(tmp_path / "README.md")
    _write(tmp_path / "target/classes/App.java")
    _write(tmp_path / ".git/hooks/pre-commit.xml")
    _write(tmp_path / "node_modules/x/y.java")

    result = ProjectScanner().scan(tmp_path)

    assert [f.relative_path for f in result.files] == [
        "pom.xml",
        "src/main/java/App.java",
        "src/main/resources/application.yml",
    ]


def test_skips_files_over_size_limit(tmp_path: Path) -> None:
    _write(tmp_path / "Small.java", "class Small {}")
    _write(tmp_path / "Huge.java", "x" * 200)

    result = ProjectScanner(max_file_bytes=100).scan(tmp_path)

    assert [f.relative_path for f in result.files] == ["Small.java"]
    assert result.skipped_large == ("Huge.java",)


def test_stops_at_file_limit(tmp_path: Path) -> None:
    for i in range(5):
        _write(tmp_path / f"C{i}.java")

    result = ProjectScanner(max_files=3).scan(tmp_path)

    assert len(result.files) == 3
    assert result.truncated


def test_marks_test_sources(tmp_path: Path) -> None:
    _write(tmp_path / "src/main/java/App.java")
    _write(tmp_path / "src/test/java/AppTest.java")

    files = {f.relative_path: f for f in ProjectScanner().scan(tmp_path).files}

    assert not files["src/main/java/App.java"].is_test
    assert files["src/test/java/AppTest.java"].is_test


def test_ignores_symlinks(tmp_path: Path) -> None:
    _write(tmp_path / "real/App.java")
    (tmp_path / "Link.java").symlink_to(tmp_path / "real/App.java")

    assert [f.relative_path for f in ProjectScanner().scan(tmp_path).files] == ["real/App.java"]
