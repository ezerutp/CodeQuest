"""Constantes de detección y escaneo de proyectos."""

from typing import Final

# Carpetas que nunca se recorren al detectar o escanear un proyecto.
IGNORED_DIRS: Final[frozenset[str]] = frozenset({
    ".git", ".idea", ".vscode", ".gradle", ".mvn",
    "target", "build", "out", "dist", "bin",
    "node_modules", "__pycache__", ".venv", "venv",
})

# Extensiones relevantes para el MVP (Java / Spring Boot).
RELEVANT_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".java", ".xml", ".gradle", ".kts", ".properties", ".yml", ".yaml",
})

# Archivos de build más grandes que esto no se leen durante la detección.
MAX_BUILD_FILE_BYTES: Final = 512 * 1024

# Archivos de código más grandes que esto se omiten (suelen ser generados).
MAX_SOURCE_FILE_BYTES: Final = 1024 * 1024

# Límite de seguridad para no recorrer repositorios gigantes por error (p. ej. $HOME).
MAX_SCANNED_FILES: Final = 20_000
