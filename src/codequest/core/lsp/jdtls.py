"""jdtls (Eclipse JDT Language Server): buscar Java, descargarlo y construir el comando de arranque.

Se descarga una versión fija (reproducible) desde download.eclipse.org, se comprueba su sha256 y se
extrae en la carpeta de datos de CodeQuest. Solo se descarga por acción explícita del estudiante.
"""

import hashlib
import logging
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

JDTLS_VERSION = "1.61.0"
DOWNLOAD_BASE = f"https://download.eclipse.org/jdtls/milestones/{JDTLS_VERSION}"
DOWNLOAD_SIZE_MB = 51  # para avisar antes de descargar
MIN_JAVA_VERSION = 21  # jdtls 1.61 necesita Java 21 o superior
_TIMEOUT_S = 30
_CHUNK = 256 * 1024

Progress = Callable[[int, int], None]  # (bytes descargados, total; 0 si se desconoce)


class InstallCancelled(Exception):
    pass


@dataclass(frozen=True, slots=True)
class JavaRuntime:
    executable: Path
    version: str  # tal como la escribe `java -version`, p. ej. "21.0.4"
    major: int

    @property
    def is_supported(self) -> bool:
        return self.major >= MIN_JAVA_VERSION


def parse_java_version(output: str) -> tuple[str, int] | None:
    """`openjdk version "21.0.4" 2024-07-16` -> ("21.0.4", 21); `"1.8.0_402"` -> ("1.8.0_402", 8)."""
    match = re.search(r'version "([^"]+)"', output)
    if match is None:
        return None
    version = match.group(1)
    numbers = re.findall(r"\d+", version)
    if not numbers:
        return None
    major = int(numbers[1]) if numbers[0] == "1" and len(numbers) > 1 else int(numbers[0])
    return version, major


def find_java(java_home: str | None = None) -> JavaRuntime | None:
    """El `java` de JAVA_HOME o, si no, el del PATH. None si no hay ninguno que funcione."""
    candidates: list[Path] = []
    if java_home:
        for name in ("java", "java.exe"):
            candidates.append(Path(java_home) / "bin" / name)
    if (on_path := shutil.which("java")) is not None:
        candidates.append(Path(on_path))
    for executable in candidates:
        if not executable.is_file():
            continue
        try:
            done = subprocess.run([str(executable), "-version"], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.info("No se pudo ejecutar %s: %s", executable, exc)
            continue
        parsed = parse_java_version(done.stderr + done.stdout)
        if parsed is not None:
            return JavaRuntime(executable, *parsed)
    return None


def config_dir_name(system: str | None = None, machine: str | None = None) -> str:
    """Carpeta de configuración de jdtls para este sistema (viene una por plataforma en el paquete)."""
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    arm = machine in ("arm64", "aarch64")
    if system == "darwin":
        return "config_mac_arm" if arm else "config_mac"
    if system == "windows":
        return "config_win"
    return "config_linux_arm" if arm else "config_linux"


@dataclass(frozen=True, slots=True)
class JdtlsInstallation:
    root: Path  # carpeta de esta versión, p. ej. <datos>/jdtls/server/1.61.0

    @property
    def is_installed(self) -> bool:
        return self.launcher() is not None and (self.root / config_dir_name()).is_dir()

    def launcher(self) -> Path | None:
        jars = sorted((self.root / "plugins").glob("org.eclipse.equinox.launcher_*.jar"))
        return jars[-1] if jars else None

    def command(self, java: JavaRuntime, workspace: Path, max_memory_mb: int = 1024) -> list[str]:
        launcher = self.launcher()
        if launcher is None:
            raise FileNotFoundError(f"jdtls no está instalado en {self.root}")
        return [
            str(java.executable),
            "-Declipse.application=org.eclipse.jdt.ls.core.id1",
            "-Dosgi.bundles.defaultStartLevel=4",
            "-Declipse.product=org.eclipse.jdt.ls.core.product",
            "-Djava.import.generatesMetadataFilesAtProjectRoot=false",
            f"-Xmx{max_memory_mb}m",
            "--add-modules=ALL-SYSTEM",
            "--add-opens", "java.base/java.util=ALL-UNNAMED",
            "--add-opens", "java.base/java.lang=ALL-UNNAMED",
            "-jar", str(launcher),
            "-configuration", str(self.root / config_dir_name()),
            "-data", str(workspace),
        ]

    def install(self, on_progress: Progress | None = None, cancel: threading.Event | None = None) -> None:
        """Descarga, verifica y extrae jdtls. Si algo falla, no deja una instalación a medias."""
        archive_name = _fetch_text(f"{DOWNLOAD_BASE}/latest.txt").strip()
        if not re.fullmatch(r"jdt-language-server-[\w.-]+\.tar\.gz", archive_name):
            raise ValueError(f"Nombre de paquete inesperado: {archive_name!r}")
        expected = _fetch_text(f"{DOWNLOAD_BASE}/{archive_name}.sha256").split()[0].lower()
        self.root.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.root.parent, prefix=".jdtls-") as tmp:
            archive = Path(tmp) / archive_name
            digest = _download(f"{DOWNLOAD_BASE}/{archive_name}", archive, on_progress, cancel)
            if digest != expected:
                raise ValueError("La descarga de jdtls está dañada (el sha256 no coincide)")
            extracted = Path(tmp) / "server"
            with tarfile.open(archive) as tar:
                tar.extractall(extracted, filter="data")  # sin rutas absolutas ni enlaces fuera
            if self.root.exists():
                shutil.rmtree(self.root)
            extracted.rename(self.root)
        log.info("jdtls %s instalado en %s", JDTLS_VERSION, self.root)

    def uninstall(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)


def _fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=_TIMEOUT_S) as response:  # noqa: S310 (URL fija https)
        return response.read(64 * 1024).decode("utf-8")


def _download(url: str, target: Path, on_progress: Progress | None, cancel: threading.Event | None) -> str:
    """Descarga a `target` y devuelve su sha256."""
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=_TIMEOUT_S) as response, target.open("wb") as out:  # noqa: S310
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while chunk := response.read(_CHUNK):
            if cancel is not None and cancel.is_set():
                raise InstallCancelled
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if on_progress is not None:
                on_progress(done, total)
    return digest.hexdigest()
