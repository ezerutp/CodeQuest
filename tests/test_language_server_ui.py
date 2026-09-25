"""Autocompletado de Java en la UI: tarjeta de Configuración y arranque de jdtls tras el análisis."""

import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from codequest.app.context import AppContext  # noqa: E402
from codequest.core.ai.availability import AIStatus  # noqa: E402
from codequest.core.lsp.client import LspClient  # noqa: E402
from codequest.core.lsp.jdtls import JavaRuntime, JdtlsInstallation, config_dir_name  # noqa: E402
from codequest.core.lsp.models import ServerState, ServerStatus  # noqa: E402
from codequest.services.java_language_service import JavaLanguageService  # noqa: E402
from codequest.services.project_service import ProjectService  # noqa: E402
from codequest.ui.formatting import language_server_indicator  # noqa: E402
from codequest.ui.main_window import MainWindow  # noqa: E402
from codequest.ui.pages.settings.page import DataPaths, SettingsPage  # noqa: E402

SERVER = Path(__file__).parent / "fixtures" / "fake_lsp_server.py"


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_indicator_texts() -> None:
    assert language_server_indicator(ServerStatus(ServerState.READY))[:2] == ("Listo", "on")
    assert "51 MB" in language_server_indicator(ServerStatus(ServerState.NOT_INSTALLED))[2]
    assert language_server_indicator(ServerStatus(ServerState.NO_JAVA, "Falta un JDK"))[2] == "Falta un JDK"


def test_settings_card_buttons_follow_the_state(qapp: QApplication) -> None:
    page = SettingsPage((), DataPaths(None, None, None, None), language_server=True)
    page.set_language_server(ServerStatus(ServerState.NOT_INSTALLED))
    assert page._java_install.isVisibleTo(page) and not page._java_uninstall.isVisibleTo(page)
    page.set_language_server(ServerStatus(ServerState.NOT_INSTALLED), download=(10 * 2**20, 51 * 2**20))
    assert not page._java_install.isEnabled() and page._java_progress.isVisibleTo(page)
    assert page._java_detail.text() == "10 de 51 MB"
    page.set_language_server(ServerStatus(ServerState.READY))
    assert not page._java_install.isVisibleTo(page) and page._java_uninstall.isVisibleTo(page)
    assert not page._java_progress.isVisibleTo(page)
    assert not SettingsPage((), DataPaths(None, None, None, None))._java_card.isVisibleTo(page)


def test_window_starts_the_server_after_the_analysis(qapp: QApplication, tmp_path: Path, shop_project: Path) -> None:
    root = tmp_path / "server"
    (root / "plugins").mkdir(parents=True)
    (root / "plugins" / "org.eclipse.equinox.launcher_1.jar").write_text("jar")
    (root / config_dir_name()).mkdir()
    service = JavaLanguageService(
        JdtlsInstallation(root), tmp_path / "projects",
        java_finder=lambda: JavaRuntime(Path("/jdk/bin/java"), "21", 21),
        client_factory=lambda command, cwd, **kw: LspClient([sys.executable, str(SERVER), "ok"], cwd=cwd, **kw))
    projects = ProjectService()
    window = MainWindow(AppContext(projects.detect(shop_project), AIStatus(False, None, "")), projects, java_ls=service)
    deadline = time.monotonic() + 10
    while not service.status.is_ready and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    for _ in range(5):
        qapp.processEvents()
    assert service.status.is_ready
    assert window._settings_page._java_status._text.text() == "Listo"
    assert (tmp_path / "projects").is_dir() and not (shop_project / ".project").exists()
    window.close()
    assert service.status.state is ServerState.STOPPED
