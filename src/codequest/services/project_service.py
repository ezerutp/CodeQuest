"""Caso de uso: detectar, escanear y analizar un proyecto. Sin Qt: se ejecuta en un worker."""

import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from codequest.core.analysis.base import FrameworkAnalyzer, SourceParser
from codequest.core.analysis.java.conventions import JavaConventionsAnalyzer
from codequest.core.analysis.java.models import JavaClass
from codequest.core.analysis.java.parser import TreeSitterJavaParser
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.snippets import CodeSnippet, SnippetRef, read_snippet
from codequest.core.analysis.spring.analyzer import SpringBootAnalyzer
from codequest.core.project.detector import ProjectDetector
from codequest.core.project.models import Framework, ProjectInfo
from codequest.core.project.scanner import ProjectScanner

log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]  # (archivos procesados, total)


class AnalysisCancelled(Exception):
    """El análisis se canceló (p. ej. el usuario cambió de proyecto)."""


class ProjectService:
    def __init__(
        self,
        detector: ProjectDetector | None = None,
        scanner: ProjectScanner | None = None,
        parsers: Sequence[SourceParser] | None = None,
        analyzers: Sequence[FrameworkAnalyzer] | None = None,
    ) -> None:
        self._detector = detector or ProjectDetector()
        self._scanner = scanner or ProjectScanner()
        self._parsers = tuple(parsers or (TreeSitterJavaParser(),))
        # El primero que soporte el proyecto gana; el último debe aceptar cualquiera.
        self._analyzers = tuple(analyzers or (SpringBootAnalyzer(), JavaConventionsAnalyzer()))

    def detect(self, root: Path) -> ProjectInfo:
        return self._detector.detect(root)

    def analyze(
        self,
        info: ProjectInfo,
        on_progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> ProjectModel:
        started = time.perf_counter()
        scan = self._scanner.scan(info.root)
        self._check(cancel)

        classes: list[JavaClass] = []
        errors: list[str] = []
        total = len(scan.files)
        for index, file in enumerate(scan.files, start=1):
            self._check(cancel)
            parser = next((p for p in self._parsers if p.supports(file)), None)
            if parser is not None:
                try:
                    classes.extend(parser.parse(file, file.read_text()))
                except Exception as exc:  # un archivo raro no debe tumbar el análisis
                    log.warning("No se pudo analizar %s: %s", file.relative_path, exc, exc_info=True)
                    errors.append(f"{file.relative_path}: {exc}")
            if on_progress:
                on_progress(index, total)

        info = self._refine_framework(info, classes)
        analyzer = next(a for a in self._analyzers if a.supports(info))
        roles = analyzer.classify(classes)

        model = ProjectModel(
            info=info,
            files=scan.files,
            classes=tuple(classes),
            roles=roles,
            errors=tuple(errors),
            duration_seconds=time.perf_counter() - started,
            truncated=scan.truncated,
            skipped_large=scan.skipped_large,
        )
        log.info("Análisis de %s: %d archivos, %d clases, %d errores en %.2fs",
                 info.name, total, len(classes), len(errors), model.duration_seconds)
        return model

    @staticmethod
    def read_source(model: ProjectModel, cls: JavaClass, whole_file: bool = False) -> CodeSnippet:
        """Código de una clase (o su archivo completo) para mostrarlo. Solo lectura."""
        if whole_file:
            return read_snippet(model.info.root, cls.file)
        return read_snippet(model.info.root, cls.file, cls.start_line, cls.end_line)

    @staticmethod
    def read_snippet(model: ProjectModel, ref: SnippetRef) -> CodeSnippet:
        return read_snippet(model.info.root, ref.file, ref.start_line, ref.end_line)

    @staticmethod
    def _refine_framework(info: ProjectInfo, classes: Sequence[JavaClass]) -> ProjectInfo:
        """Detecta Spring Boot por @SpringBootApplication si el build file no lo reveló (multi-módulo)."""
        if info.framework is Framework.NONE and any(c.has_annotation("SpringBootApplication") for c in classes):
            return replace(info, framework=Framework.SPRING_BOOT)
        return info

    @staticmethod
    def _check(cancel: threading.Event | None) -> None:
        if cancel is not None and cancel.is_set():
            raise AnalysisCancelled
