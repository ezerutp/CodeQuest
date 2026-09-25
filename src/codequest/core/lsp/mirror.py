"""Copia espejo del proyecto para el servidor de lenguaje.

jdtls escribe `.project`, `.classpath`, `.settings/` y `target/` en la carpeta que importa, aunque se
le pida lo contrario. Por eso nunca ve el proyecto real: trabaja sobre esta copia, en la carpeta de
datos de CodeQuest. Del proyecto solo se lee; la copia se actualiza por tamaño y fecha.
"""

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from codequest.core.project.constants import IGNORED_DIRS, MAX_SOURCE_FILE_BYTES

log = logging.getLogger(__name__)

# Lo que jdtls necesita: el código y la configuración de Maven/Gradle (incluidos los recursos).
MIRRORED_SUFFIXES = frozenset({".java", ".xml", ".gradle", ".kts", ".properties", ".yml", ".yaml", ".toml"})
MAX_MIRRORED_FILES = 20_000  # mismo límite de seguridad que el escáner


@dataclass(frozen=True, slots=True)
class MirrorStats:
    copied: int
    removed: int
    total: int


def sync_mirror(project: Path, mirror: Path) -> MirrorStats:
    """Deja en `mirror` una copia de los archivos relevantes de `project` y borra los que sobran."""
    project, mirror = project.resolve(), mirror.resolve()
    if mirror == project or project in mirror.parents or mirror in project.parents:
        raise ValueError(f"La copia espejo {mirror} no puede estar dentro del proyecto ni contenerlo")
    wanted: set[Path] = set()
    copied = 0
    for directory, dirnames, filenames in os.walk(project):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS and not d.startswith("."))
        for name in filenames:
            source = Path(directory, name)
            if source.suffix not in MIRRORED_SUFFIXES or source.is_symlink():
                continue
            try:
                stat = source.stat()
            except OSError:
                continue
            if stat.st_size > MAX_SOURCE_FILE_BYTES:
                continue
            relative = source.relative_to(project)
            wanted.add(relative)
            if len(wanted) > MAX_MIRRORED_FILES:
                raise ValueError(f"El proyecto tiene más de {MAX_MIRRORED_FILES} archivos de código")
            target = mirror / relative
            if _is_current(target, stat):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)  # copia también la fecha: así se detectan cambios
            copied += 1
    removed = _remove_stale(mirror, wanted)
    log.info("Copia espejo de %s: %d copiados, %d borrados, %d en total", project.name, copied, removed,
             len(wanted))
    return MirrorStats(copied, removed, len(wanted))


def _is_current(target: Path, stat: os.stat_result) -> bool:
    try:
        current = target.stat()
    except OSError:
        return False
    return current.st_size == stat.st_size and int(current.st_mtime) == int(stat.st_mtime)


def _remove_stale(mirror: Path, wanted: set[Path]) -> int:
    """Borra de la copia lo que ya no está en el proyecto. Lo que genera jdtls (`.project`, `target/`…)
    no se toca: no tiene una extensión copiada o está en una carpeta ignorada."""
    removed = 0
    for directory, dirnames, filenames in os.walk(mirror):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
        for name in filenames:
            path = Path(directory, name)
            if path.suffix in MIRRORED_SUFFIXES and path.relative_to(mirror) not in wanted:
                path.unlink()
                removed += 1
    return removed
