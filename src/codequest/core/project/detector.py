"""Detección rápida del tipo de proyecto a partir de marcadores en disco.

Solo lee: nunca escribe nada dentro del proyecto analizado.
"""

import configparser
import json
import logging
import re
from pathlib import Path

from codequest.core.project.constants import IGNORED_DIRS, MAX_BUILD_FILE_BYTES
from codequest.core.project.models import BuildTool, Framework, Language, ProjectInfo

log = logging.getLogger(__name__)

MARKERS: tuple[str, ...] = (
    ".git", "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "settings.gradle.kts", "package.json", "src",
)
_MAVEN_FILES = ("pom.xml",)
_GRADLE_FILES = ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
_SPRING_BOOT_HINTS = ("org.springframework.boot", "spring-boot")
_REACT_HINTS = ("react", "react-dom")
_TS_EXTENSIONS = (".ts", ".tsx")
_CREDENTIALS_IN_URL = re.compile(r"(?<=://)[^/@]+@")
_MAX_DISCOVERY_DEPTH = 3


class ProjectDetector:
    """Decide qué es un directorio: ¿código?, ¿Java?, ¿Spring Boot?, ¿React?, ¿Maven/Gradle?"""

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
        language = self._detect_language(root)
        framework = self._detect_framework(root, build_tool)

        warnings: list[str] = []
        if not markers:
            warnings.append(
                "No se encontraron marcadores de proyecto (.git, pom.xml, build.gradle, package.json, src/)."
            )
        if language is Language.UNKNOWN:
            warnings.append("No se encontraron archivos .java ni .ts/.tsx.")

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

    def detect_all(self, root: Path) -> list[ProjectInfo]:
        """Descubre subproyectos dentro de un árbol (p. ej. backend/ + frontend/).

        Busca marcadores de proyecto (pom.xml, build.gradle*, package.json) en root
        y subdirectorios hasta _MAX_DISCOVERY_DEPTH niveles. Devuelve un ProjectInfo
        por cada subproyecto encontrado, ordenado por nombre de carpeta.
        """
        root = root.expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"No es un directorio: {root}")

        subproject_roots = self._find_subproject_roots(root)
        if not subproject_roots:
            # No hay subproyectos: root es el proyecto (aunque sea desconocido)
            return [self.detect(root)]

        infos = [self.detect(r) for r in sorted(subproject_roots)]
        log.info("Detectados %d subproyectos en %s", len(infos), root)
        return infos

    def _find_subproject_roots(self, root: Path) -> set[Path]:
        """Busca carpetas con marcadores de build (pom.xml, build.gradle*, package.json)."""
        build_files = _MAVEN_FILES + _GRADLE_FILES + ("package.json",)
        found: set[Path] = set()

        for dirpath, dirnames, filenames in root.walk(on_error=lambda e: log.debug("walk: %s", e)):
            current = Path(dirpath)
            depth = len(current.relative_to(root).parts)
            if depth >= _MAX_DISCOVERY_DEPTH:
                dirnames.clear()
                continue
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
            if any(f in filenames for f in build_files):
                found.add(current)
                # No buscar más profundo dentro de un subproyecto encontrado
                dirnames.clear()

        # Si root mismo tiene marcadores, incluirlo
        if any((root / f).is_file() for f in build_files):
            found.add(root)

        return found

    @staticmethod
    def _detect_build_tool(root: Path) -> BuildTool:
        if any((root / f).is_file() for f in _MAVEN_FILES):
            return BuildTool.MAVEN
        if any((root / f).is_file() for f in _GRADLE_FILES):
            return BuildTool.GRADLE
        return BuildTool.NONE

    def _detect_language(self, root: Path) -> Language:
        if self._has_java_sources(root):
            return Language.JAVA
        if self._has_typescript_sources(root):
            return Language.TYPESCRIPT
        return Language.UNKNOWN

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

    def _has_typescript_sources(self, root: Path) -> bool:
        visited = 0
        for dirpath, dirnames, filenames in root.walk(on_error=lambda e: log.debug("walk: %s", e)):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
            if any(f.endswith(_TS_EXTENSIONS) for f in filenames):
                return True
            visited += len(filenames) + len(dirnames)
            if visited > self._java_search_limit:
                log.debug("Búsqueda de .ts/.tsx cortada tras %d entradas en %s", visited, dirpath)
                return False
        return False

    def _detect_framework(self, root: Path, build_tool: BuildTool) -> Framework:
        # Spring Boot: en build files de Maven/Gradle
        if build_tool in (BuildTool.MAVEN, BuildTool.GRADLE):
            files = _MAVEN_FILES if build_tool is BuildTool.MAVEN else _GRADLE_FILES
            for name in files:
                text = self._read_small_text(root / name)
                if text and any(hint in text for hint in _SPRING_BOOT_HINTS):
                    return Framework.SPRING_BOOT
        # React: en package.json
        pkg_json = self._read_small_text(root / "package.json")
        if pkg_json and self._package_has_react(pkg_json):
            return Framework.REACT
        return Framework.NONE

    @staticmethod
    def _package_has_react(pkg_json: str) -> bool:
        """True si package.json declara react o react-dom como dependencia."""
        try:
            data = json.loads(pkg_json)
        except (json.JSONDecodeError, TypeError):
            return False
        for section in ("dependencies", "devDependencies"):
            deps = data.get(section, {})
            if isinstance(deps, dict) and any(hint in deps for hint in _REACT_HINTS):
                return True
        return False

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
