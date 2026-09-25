import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from codequest.core.lsp import jdtls
from codequest.core.lsp.jdtls import JavaRuntime, JdtlsInstallation, config_dir_name, parse_java_version


@pytest.mark.parametrize(("output", "expected"), [
    ('openjdk version "21.0.12.1" 2026-08-18 LTS', ("21.0.12.1", 21)),
    ('java version "1.8.0_402"', ("1.8.0_402", 8)),
    ('openjdk version "17" 2021-09-14', ("17", 17)),
    ("no es java", None),
])
def test_parse_java_version(output: str, expected: tuple[str, int] | None) -> None:
    assert parse_java_version(output) == expected


def test_config_dir_per_platform() -> None:
    assert config_dir_name("Linux", "x86_64") == "config_linux"
    assert config_dir_name("Linux", "aarch64") == "config_linux_arm"
    assert config_dir_name("Darwin", "arm64") == "config_mac_arm"
    assert config_dir_name("Windows", "AMD64") == "config_win"


def _fake_server_tree(root: Path) -> None:
    (root / "plugins").mkdir(parents=True)
    (root / "plugins" / "org.eclipse.equinox.launcher_1.8.0.jar").write_text("jar")
    (root / config_dir_name()).mkdir()


def test_command_uses_our_workspace_and_config(tmp_path: Path) -> None:
    install = JdtlsInstallation(tmp_path / "server")
    assert not install.is_installed
    _fake_server_tree(install.root)
    assert install.is_installed
    command = install.command(JavaRuntime(Path("/jdk/bin/java"), "21", 21), tmp_path / "ws")
    assert command[0] == "/jdk/bin/java"
    assert command[command.index("-data") + 1] == str(tmp_path / "ws")
    assert command[command.index("-configuration") + 1] == str(install.root / config_dir_name())
    assert "-Djava.import.generatesMetadataFilesAtProjectRoot=false" in command


def _archive() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name in ("plugins/org.eclipse.equinox.launcher_1.8.0.jar", f"{config_dir_name()}/config.ini"):
            data = b"x"
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class _Response(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _serve(monkeypatch: pytest.MonkeyPatch, archive: bytes, sha: str) -> list[str]:
    name = "jdt-language-server-1.61.0-202609031315.tar.gz"
    urls: list[str] = []
    files = {"latest.txt": name.encode(), name: archive, f"{name}.sha256": f"{sha}  {name}".encode()}

    def urlopen(url: str, timeout: float) -> _Response:
        urls.append(url)
        return _Response(files[url.rsplit("/", 1)[1]])

    monkeypatch.setattr(jdtls.urllib.request, "urlopen", urlopen)
    return urls


def test_install_downloads_verifies_and_extracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = _archive()
    urls = _serve(monkeypatch, archive, hashlib.sha256(archive).hexdigest())
    progress: list[tuple[int, int]] = []
    install = JdtlsInstallation(tmp_path / "jdtls" / "server" / "1.61.0")
    install.install(on_progress=lambda done, total: progress.append((done, total)))
    assert install.is_installed and progress[-1] == (len(archive), len(archive))
    assert all(url.startswith("https://download.eclipse.org/jdtls/milestones/1.61.0/") for url in urls)
    assert [p.name for p in install.root.parent.iterdir()] == ["1.61.0"]  # sin temporales
    install.uninstall()
    assert not install.root.exists()


def test_corrupted_download_leaves_nothing_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _archive(), "0" * 64)
    install = JdtlsInstallation(tmp_path / "server" / "1.61.0")
    with pytest.raises(ValueError, match="sha256"):
        install.install()
    assert not install.is_installed and list(install.root.parent.iterdir()) == []
