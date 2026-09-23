"""Detección rápida del tipo de proyecto a partir de marcadores en disco.

Solo lee: nunca escribe nada dentro del proyecto analizado.
"""

import configparser
import logging
import re
from pathlib import Path

from codequest.core.project.constants import IGNORED_DIRS, MAX_BUILD_FILE_BYTES
from codequest.core.project.models import BuildTool, Framework, Language, ProjectInfo

log = logging.getLogger(__name__)

MARKERS: tuple[str, ...] = (
    ".git", "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "settings.gradle.kts", "src",
)
_MAVEN_FILES = ("pom.xml",)
_GRADLE_FILES = ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
_SPRING_BOOT_HINTS = ("org.springframework.boot", "spring-boot")
_CREDENTIALS_IN_URL = re.compile(r"(?<=://)[^/@]+@")


class ProjectDetector:
    """Decide qué es un directorio: ¿código?, ¿Java?, ¿Spring Boot?, ¿Maven o Gradle?"""

    def __init__(self, java_search_limit: int = 5000) -> None:
        # Máximo de entradas a visitar buscando un .java, para no recorrer
        # repositorios enormes solo para detectar el lenguaje.
        self._java_search_limit = java_search_limit

    def detect(self, root: Path) -> ProjectInfo:
        root = root.expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"No es un directorio: {root}")

        markers = tuple(m for m in MARKERS if (root / m).exists())
        build_tool = self._detect_build_tool(root)
        language = Language.JAVA if self._has_java_sources(root) else Language.UNKNOWN
        framework = self._detect_framework(root, build_tool)

        warnings: list[str] = []
        if not markers:
            warnings.append("No se encontraron marcadores de proyecto (.git, pom.xml, build.gradle, src/).")
        if language is Language.UNKNOWN:
            warnings.append("No se encontraron archivos .java.")

        info = ProjectInfo(
            root=root,
            name=root.name,
            markers=markers,
            language=language,
            framework=framework,
            build_tool=build_tool,
            git_remote=self._read_git_remote(root),
            warnings=tuple(warnings),
        )
        log.info("Proyecto detectado: %s (%s)", info.name, " · ".join(info.stack) or "tipo desconocido")
        return info

    @staticmethod
    def _detect_build_tool(root: Path) -> BuildTool:
        if any((root / f).is_file() for f in _MAVEN_FILES):
            return BuildTool.MAVEN
        if any((root / f).is_file() for f in _GRADLE_FILES):
            return BuildTool.GRADLE
        return BuildTool.NONE

    def _has_java_sources(self, root: Path) -> bool:
        if (root / "src" / "main" / "java").is_dir():
            return True
        visited = 0
        for dirpath, dirnames, filenames in root.walk(on_error=lambda e: log.debug("walk: %s", e)):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
            if any(f.endswith(".java") for f in filenames):
                return True
            visited += len(filenames) + len(dirnames)
            if visited > self._java_search_limit:
                log.debug("Búsqueda de .java cortada tras %d entradas en %s", visited, dirpath)
                return False
        return False

    def _detect_framework(self, root: Path, build_tool: BuildTool) -> Framework:
        files = _MAVEN_FILES if build_tool is BuildTool.MAVEN else _GRADLE_FILES
        for name in files:
            text = self._read_small_text(root / name)
            if text and any(hint in text for hint in _SPRING_BOOT_HINTS):
                return Framework.SPRING_BOOT
        return Framework.NONE

    @staticmethod
    def _read_small_text(path: Path) -> str | None:
        try:
            if not path.is_file() or path.stat().st_size > MAX_BUILD_FILE_BYTES:
                return None
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log.warning("No se pudo leer %s: %s", path, exc)
            return None

    @classmethod
    def _read_git_remote(cls, root: Path) -> str | None:
        """Lee la URL de `origin` desde .git/config sin ejecutar git. Elimina credenciales."""
        text = cls._read_small_text(root / ".git" / "config")
        if not text:
            return None
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        try:
            parser.read_string(text)
        except configparser.Error as exc:
            log.debug("No se pudo parsear .git/config: %s", exc)
            return None
        url = parser.get('remote "origin"', "url", fallback=None)
        return _CREDENTIALS_IN_URL.sub("", url) if url else None
