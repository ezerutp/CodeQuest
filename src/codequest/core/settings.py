"""Ajustes del usuario, guardados en settings.json en la carpeta de datos de CodeQuest."""

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Settings:
    ai_enabled: bool = True  # si hay API key, el usuario puede apagar la IA igualmente
    ai_model: str | None = None  # None = el modelo por defecto del proveedor

    def with_changes(self, **changes: object) -> "Settings":
        return replace(self, **changes)


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Settings:
        """Nunca falla: un archivo ausente o dañado devuelve los valores por defecto."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Settings()
        except (OSError, ValueError) as exc:
            log.warning("Ajustes ilegibles en %s (%s); se usan los valores por defecto", self.path, exc)
            return Settings()
        if not isinstance(data, dict):
            return Settings()
        known = {f.name: f for f in fields(Settings)}
        values = {}
        for name, value in data.items():
            if name not in known:
                continue  # ajustes de otra versión: se ignoran
            if name == "ai_enabled" and isinstance(value, bool):
                values[name] = value
            elif name == "ai_model" and (value is None or (isinstance(value, str) and value.strip())):
                values[name] = value.strip() if isinstance(value, str) else None
        return Settings(**values)

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".settings-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(asdict(settings), handle, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
