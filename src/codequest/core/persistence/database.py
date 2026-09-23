"""SQLite local de CodeQuest. Vive en la carpeta de datos del usuario, nunca en el proyecto."""

import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

# Cada migración lleva la base de la versión i a la i+1. Solo se añaden al final.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE projects (
        id          TEXT PRIMARY KEY,   -- sha256(ruta canónica)[:16]
        name        TEXT NOT NULL,
        root_path   TEXT NOT NULL,
        git_remote  TEXT,
        first_seen  TEXT NOT NULL,
        last_opened TEXT NOT NULL
    );
    CREATE TABLE sessions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        mode        TEXT NOT NULL,
        scope       TEXT,               -- clase practicada, o NULL para todo el proyecto
        total       INTEGER NOT NULL,
        started_at  TEXT NOT NULL,
        ended_at    TEXT
    );
    CREATE TABLE attempts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        question_key TEXT NOT NULL,     -- clave estable; nunca se guarda código
        concept_id   TEXT NOT NULL,
        class_name   TEXT NOT NULL,
        outcome      TEXT NOT NULL,     -- correct | incorrect | skipped
        answered_at  TEXT NOT NULL
    );
    CREATE INDEX attempts_by_concept ON attempts(project_id, concept_id, answered_at);
    CREATE INDEX attempts_by_time ON attempts(project_id, answered_at);
    """,
)


class Database:
    def __init__(self, path: Path | str) -> None:
        """`path` puede ser ":memory:" (tests)."""
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        # Una sola conexión, usada desde el hilo principal: las escrituras son pocas y rápidas.
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    @property
    def version(self) -> int:
        return self.connection.execute("PRAGMA user_version").fetchone()[0]

    def _migrate(self) -> None:
        current = self.version
        if current > len(MIGRATIONS):
            raise sqlite3.DatabaseError(f"Base de datos de una versión más nueva de CodeQuest ({current})")
        for version, script in enumerate(MIGRATIONS[current:], start=current + 1):
            with self.connection:  # transacción: o se aplica entera o nada
                self.connection.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {version};")
            log.info("Base de datos migrada a la versión %d", version)

    def close(self) -> None:
        self.connection.close()
