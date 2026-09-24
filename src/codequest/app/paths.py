"""Rutas de datos de CodeQuest en la máquina del usuario (nunca dentro del proyecto analizado)."""

from pathlib import Path

from platformdirs import user_data_dir, user_log_dir

from codequest.app.constants import APP_SLUG


def data_dir() -> Path:
    return Path(user_data_dir(APP_SLUG, appauthor=False))


def knowledge_dir() -> Path:
    """Conceptos añadidos por el usuario o generados con IA (un YAML por archivo)."""
    return data_dir() / "knowledge"


def database_path() -> Path:
    """Progreso local (SQLite). Solo claves de preguntas y resultados, nunca código."""
    return data_dir() / "codequest.db"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def log_dir() -> Path:
    return Path(user_log_dir(APP_SLUG, appauthor=False))
