from pathlib import Path

import pytest

from codequest.core.analysis.snippets import read_snippet
from codequest.services.project_service import ProjectService


def test_reads_line_range(tmp_path: Path) -> None:
    (tmp_path / "A.java").write_text("l1\nl2\nl3\nl4\n")

    snippet = read_snippet(tmp_path, "A.java", 2, 3)

    assert (snippet.start_line, snippet.end_line, snippet.text) == (2, 3, "l2\nl3")


def test_clamps_range_to_file(tmp_path: Path) -> None:
    (tmp_path / "A.java").write_text("l1\nl2")

    snippet = read_snippet(tmp_path, "A.java", 0, 99)

    assert (snippet.start_line, snippet.end_line, snippet.line_count) == (1, 2, 2)


def test_rejects_paths_outside_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "secret.txt").write_text("x")

    with pytest.raises(ValueError):
        read_snippet(project, "../secret.txt")


def test_service_reads_class_source(shop_project: Path) -> None:
    service = ProjectService()
    model = service.analyze(service.detect(shop_project))
    controller = next(c for c in model.classes if c.name == "UserController")

    snippet = service.read_source(model, controller)

    assert snippet.start_line == controller.start_line
    assert snippet.text.startswith("@RestController")
    assert snippet.text.rstrip().endswith("}")
    assert service.read_source(model, controller, whole_file=True).text.startswith("package")
