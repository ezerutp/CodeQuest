"""Configuración de logging con redacción de secretos."""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from codequest.app.paths import log_dir as default_log_dir

# Cadenas con forma de API key (Anthropic, OpenAI...). Defensa en profundidad:
# el código nunca debería loguear una key, pero si ocurre, se enmascara.
_SECRET_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9_\-]{8})[A-Za-z0-9_\-]+")


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _SECRET_PATTERN.sub(r"\1…[REDACTED]", message)
        if redacted != message:
            record.msg, record.args = redacted, None
        return True


def setup_logging(debug: bool = False) -> Path:
    """Configura consola + archivo rotativo. Devuelve la ruta del log."""
    log_dir = default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "codequest.log"

    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    redact = RedactSecretsFilter()

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if debug else logging.WARNING)
    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in (console, file_handler):
        handler.setFormatter(formatter)
        handler.addFilter(redact)
        root.addHandler(handler)

    return log_file
