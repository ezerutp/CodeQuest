"""Instalación y comando del servidor de lenguaje TypeScript (typescript-language-server).

Se instala como paquete npm en la carpeta de datos de CodeQuest. Es el mismo
servidor que usa VS Code para TypeScript/React.
"""

import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

TSSERVER_VERSION = "4.3.0"
TSSERVER_PACKAGE = "typescript-language-server"


class TypeScriptServerInstallation:
    """Gestiona la instalación de typescript-language-server."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    @property
    def command(self) -> list[str]:
        """Comando para arrancar el servidor."""
        return ["npx", "--yes", f"{TSSERVER_PACKAGE}@{TSSERVER_VERSION}", "--stdio"]

    @property
    def is_installed(self) -> bool:
        """True si npx está disponible (el servidor se descarga bajo demanda)."""
        return shutil.which("npx") is not None

    @property
    def version(self) -> str:
        return TSSERVER_VERSION

    @property
    def size_mb(self) -> int:
        return 50  # aproximado: typescript + tipos + tsserver
