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
