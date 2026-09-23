"""Modelos que describen el proyecto analizado."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Language(StrEnum):
    JAVA = "Java"
    UNKNOWN = "Desconocido"


class Framework(StrEnum):
    SPRING_BOOT = "Spring Boot"
    NONE = "Sin framework"


class BuildTool(StrEnum):
    MAVEN = "Maven"
    GRADLE = "Gradle"
    NONE = "Sin build tool"


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    """Identidad y tipo del proyecto. Inmutable: se recrea si cambia el proyecto."""

    root: Path
    name: str
    markers: tuple[str, ...] = ()
    language: Language = Language.UNKNOWN
    framework: Framework = Framework.NONE
    build_tool: BuildTool = BuildTool.NONE
    git_remote: str | None = None
    warnings: tuple[str, ...] = field(default=())

    @property
    def is_code_project(self) -> bool:
        return bool(self.markers) or self.language is not Language.UNKNOWN

    @property
    def is_supported(self) -> bool:
        """El MVP solo sabe generar ejercicios para proyectos Java."""
        return self.language is Language.JAVA

    @property
    def stack(self) -> tuple[str, ...]:
        """Etiquetas legibles, p. ej. ("Spring Boot", "Java", "Maven")."""
        parts: list[str] = []
        if self.framework is not Framework.NONE:
            parts.append(self.framework.value)
        if self.language is not Language.UNKNOWN:
            parts.append(self.language.value)
        if self.build_tool is not BuildTool.NONE:
            parts.append(self.build_tool.value)
        return tuple(parts)


@dataclass(frozen=True, slots=True)
class SourceFile:
    """Archivo relevante del proyecto. El contenido se lee bajo demanda y solo en lectura."""

    path: Path
    relative_path: str  # formato POSIX, relativo a la raíz del proyecto
    size: int

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    @property
    def is_test(self) -> bool:
        """Heurística de Maven/Gradle: todo lo que cuelga de src/test/."""
        return "/src/test/" in f"/{self.relative_path}"

    def read_text(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace")
