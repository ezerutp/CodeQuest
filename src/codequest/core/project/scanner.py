"""Recorrido del árbol del proyecto. Solo lectura."""

import logging
from dataclasses import dataclass
from pathlib import Path

from codequest.core.project.constants import (
    IGNORED_DIRS,
    MAX_SCANNED_FILES,
    MAX_SOURCE_FILE_BYTES,
    RELEVANT_EXTENSIONS,
)
from codequest.core.project.models import SourceFile

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScanResult:
    files: tuple[SourceFile, ...]
    skipped_large: tuple[str, ...] = ()
    truncated: bool = False


class ProjectScanner:
    """Recorre el proyecto y devuelve los archivos relevantes. No los lee ni los interpreta."""

    def __init__(
        self,
        extensions: frozenset[str] = RELEVANT_EXTENSIONS,
        ignored_dirs: frozenset[str] = IGNORED_DIRS,
        max_file_bytes: int = MAX_SOURCE_FILE_BYTES,
        max_files: int = MAX_SCANNED_FILES,
    ) -> None:
        self._extensions = extensions
        self._ignored_dirs = ignored_dirs
        self._max_file_bytes = max_file_bytes
        self._max_files = max_files

    def scan(self, root: Path) -> ScanResult:
        root = root.resolve()
        files: list[SourceFile] = []
        skipped_large: list[str] = []
        truncated = False

        for dirpath, dirnames, filenames in root.walk(on_error=lambda e: log.warning("No se pudo leer: %s", e)):
            dirnames[:] = sorted(d for d in dirnames if d not in self._ignored_dirs)
            for name in sorted(filenames):
                path = dirpath / name
                if path.suffix.lower() not in self._extensions or path.is_symlink():
                    continue
                try:
                    size = path.stat().st_size
                except OSError as exc:
                    log.warning("No se pudo leer %s: %s", path, exc)
                    continue
                relative = path.relative_to(root).as_posix()
                if size > self._max_file_bytes:
                    skipped_large.append(relative)
                    continue
                files.append(SourceFile(path=path, relative_path=relative, size=size))
                if len(files) >= self._max_files:
                    log.warning("Escaneo detenido: más de %d archivos en %s", self._max_files, root)
                    truncated = True
                    break
            if truncated:
                break

        files.sort(key=lambda f: f.relative_path)
        log.info("Escaneados %d archivos relevantes en %s", len(files), root)
        return ScanResult(tuple(files), tuple(skipped_large), truncated)
