import threading
from dataclasses import replace
from pathlib import Path

import pytest

from codequest.core.analysis.base import SourceParser
from codequest.core.analysis.roles import ComponentRole as R
from codequest.core.project.models import Framework
from codequest.services.project_service import AnalysisCancelled, ProjectService


def test_analyzes_spring_project_end_to_end(shop_project: Path) -> None:
    service = ProjectService()
    progress: list[tuple[int, int]] = []

    model = service.analyze(service.detect(shop_project), on_progress=lambda d, t: progress.append((d, t)))

    counts = model.role_counts()
    assert counts[R.ENTITY] == 2
    assert counts[R.CONTROLLER] == 1
    assert counts[R.SERVICE] == 1
    assert counts[R.REPOSITORY] == 2
    assert counts[R.ENUM] == 1
    # La clase de test existe en el modelo, pero no cuenta en las estadísticas.
    assert any(c.is_test for c in model.classes)
    assert all(not c.is_test for c in model.main_classes)
    # target/ se ignora; application.properties y pom.xml cuentan como archivos.
    paths = [f.relative_path for f in model.files]
    assert "pom.xml" in paths and not any(p.startswith("target/") for p in paths)
    assert progress[-1] == (len(model.files), len(model.files))
    assert model.annotation_usage()["Transactional"] == 2
    assert model.errors == ()


def test_detects_spring_boot_from_annotation_when_build_file_is_silent(shop_project: Path) -> None:
    service = ProjectService()
    info = replace(service.detect(shop_project), framework=Framework.NONE)

    model = service.analyze(info)

    assert model.info.framework is Framework.SPRING_BOOT
    assert model.role_counts()[R.CONTROLLER] == 1


def test_cancellation(shop_project: Path) -> None:
    service = ProjectService()
    cancel = threading.Event()

    def cancel_after_first(done: int, total: int) -> None:
        cancel.set()

    with pytest.raises(AnalysisCancelled):
        service.analyze(service.detect(shop_project), on_progress=cancel_after_first, cancel=cancel)


def test_parser_errors_are_collected_not_raised(shop_project: Path) -> None:
    class ExplodingParser(SourceParser):
        def supports(self, file):
            return file.relative_path.endswith("User.java")

        def parse(self, file, text):
            raise ValueError("boom")

    service = ProjectService(parsers=[ExplodingParser()])

    model = service.analyze(service.detect(shop_project))

    assert model.errors and "boom" in model.errors[0]


def test_analysis_never_writes_inside_project(shop_project: Path) -> None:
    before = sorted((p, p.stat().st_mtime_ns) for p in shop_project.rglob("*"))

    service = ProjectService()
    service.analyze(service.detect(shop_project))

    assert sorted((p, p.stat().st_mtime_ns) for p in shop_project.rglob("*")) == before
