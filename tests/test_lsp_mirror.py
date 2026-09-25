from pathlib import Path

import pytest

from codequest.core.lsp.mirror import sync_mirror


def _project(root: Path) -> Path:
    files = {
        "pom.xml": "<project/>",
        "src/main/java/com/x/A.java": "class A {}",
        "src/main/resources/application.yml": "server: {}",
        "src/main/resources/static/logo.png": "png",
        "target/classes/A.class": "bin",
        ".git/config": "[core]",
        ".idea/misc.xml": "<x/>",
    }
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root


def _tree(root: Path) -> dict[str, float]:
    return {str(p.relative_to(root)): p.stat().st_mtime for p in root.rglob("*")}


def test_copies_code_and_build_files_only(tmp_path: Path) -> None:
    project = _project(tmp_path / "project")
    before = _tree(project)
    stats = sync_mirror(project, tmp_path / "mirror")
    copied = {str(p.relative_to(tmp_path / "mirror")) for p in (tmp_path / "mirror").rglob("*") if p.is_file()}
    assert copied == {"pom.xml", "src/main/java/com/x/A.java", "src/main/resources/application.yml"}
    assert stats.copied == stats.total == 3
    assert _tree(project) == before  # el proyecto es de solo lectura


def test_updates_changes_and_removes_deleted_files_but_keeps_server_files(tmp_path: Path) -> None:
    project, mirror = _project(tmp_path / "project"), tmp_path / "mirror"
    sync_mirror(project, mirror)
    (mirror / ".project").write_text("jdtls")  # lo que genera jdtls en la copia
    (mirror / "target").mkdir()
    (mirror / "target" / "B.java").write_text("generado")
    (project / "src/main/java/com/x/A.java").write_text("class A { int x; }")
    (project / "src/main/resources/application.yml").unlink()

    stats = sync_mirror(project, mirror)
    assert (stats.copied, stats.removed) == (1, 1)
    assert (mirror / "src/main/java/com/x/A.java").read_text() == "class A { int x; }"
    assert (mirror / ".project").exists() and (mirror / "target" / "B.java").exists()
    assert sync_mirror(project, mirror).copied == 0


def test_mirror_can_not_live_inside_the_project(tmp_path: Path) -> None:
    project = _project(tmp_path / "project")
    for mirror in (project / "copia", project, tmp_path):
        with pytest.raises(ValueError):
            sync_mirror(project, mirror)
