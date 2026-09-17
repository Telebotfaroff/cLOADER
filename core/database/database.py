"""Small SQLite database wrapper used by cLOADER."""

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    original_filename TEXT,
    custom_filename TEXT,
    final_filename TEXT,
    status TEXT NOT NULL,
    selected_providers TEXT NOT NULL DEFAULT '[]',
    file_path TEXT,
    file_size INTEGER NOT NULL DEFAULT 0,
    downloaded_bytes INTEGER NOT NULL DEFAULT 0,
    download_speed REAL NOT NULL DEFAULT 0,
    download_progress REAL NOT NULL DEFAULT 0,
    download_eta REAL,
    file_sha256 TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS uploads (
    task_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    uploaded_bytes INTEGER NOT NULL DEFAULT 0,
    total_bytes INTEGER NOT NULL DEFAULT 0,
    speed REAL NOT NULL DEFAULT 0,
    url TEXT,
    error TEXT,
    upload_id TEXT,
    started_at TEXT,
    completed_at TEXT,
    PRIMARY KEY (task_id, provider_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
"""


class Database:
    """Manage the cLOADER SQLite connection and schema."""

    def __init__(self, path: str | Path = "data/cloader.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")

    def initialize(self) -> None:
        """Create tables and indexes if they do not exist."""
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Database":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.close()
