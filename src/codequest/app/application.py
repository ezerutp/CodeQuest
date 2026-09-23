"""Punto de entrada: argumentos, logging, detección del proyecto y arranque de Qt."""

import argparse
import logging
import sys
from pathlib import Path

from codequest import __version__
from codequest.app.constants import APP_NAME, APP_SLUG, APP_TAGLINE
from codequest.app.context import AppContext
from codequest.app.logging_setup import setup_logging
from codequest.core.ai.availability import detect_ai_status
from codequest.core.project.detector import ProjectDetector

log = logging.getLogger(__name__)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=APP_SLUG, description=f"{APP_NAME}: {APP_TAGLINE}")
    parser.add_argument("path", nargs="?", type=Path,
                        help="Proyecto a estudiar (por defecto, el directorio actual).")
    parser.add_argument("--debug", action="store_true", help="Muestra logs detallados en la terminal.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log_file = setup_logging(debug=args.debug)
    log.info("%s %s iniciando (log: %s)", APP_NAME, __version__, log_file)

    root = args.path if args.path else Path.cwd()
    detector = ProjectDetector()
    try:
        project = detector.detect(root)
    except OSError as exc:
        print(f"{APP_SLUG}: {exc}", file=sys.stderr)
        return 2

    context = AppContext(project=project, ai=detect_ai_status())

    # Qt se importa aquí para que --help/--version no necesiten cargarlo.
    from PySide6.QtWidgets import QApplication

    from codequest.ui.main_window import MainWindow
    from codequest.ui.theme import DARK, load_stylesheet

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")  # base consistente entre sistemas; QSS la refina
    app.setStyleSheet(load_stylesheet(DARK))

    window = MainWindow(context, detect_project=detector.detect)
    window.show()
    return app.exec()
