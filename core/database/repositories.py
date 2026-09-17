"""Database repositories for cLOADER domain models."""

import json
from datetime import datetime

from ..models import Task, TaskStatus, UploadResult, UploadStatus
from .database import Database


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class TaskRepository:
    """Persist and retrieve tasks and their upload results."""

    def __init__(self, database: Database) -> None:
        self.db = database
        self.db.initialize()

    def save(self, task: Task) -> None:
        self.db.connection.execute(
            """INSERT OR REPLACE INTO tasks
            (id, source_url, original_filename, custom_filename, final_filename,
             status, selected_providers, file_path, file_size, downloaded_bytes,
             download_speed, download_progress, download_eta, file_sha256,
             created_at, started_at, completed_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.id, task.source_url, task.original_filename, task.custom_filename,
                task.final_filename, task.status.value, json.dumps(task.selected_providers),
                task.file_path, task.file_size, task.downloaded_bytes,
                task.download_speed, task.download_progress, task.download_eta,
                task.file_sha256, _dt(task.created_at), _dt(task.started_at),
                _dt(task.completed_at), task.error,
            ),
        )
        self.db.connection.execute("DELETE FROM uploads WHERE task_id = ?", (task.id,))
        self._save_uploads(task)
        self.db.connection.commit()

    def _save_uploads(self, task: Task) -> None:
        for upload in task.uploads:
            self.db.connection.execute(
                """INSERT INTO uploads
                (task_id, provider_id, status, progress, uploaded_bytes, total_bytes,
                 speed, url, error, upload_id, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    upload.task_id, upload.provider_id, upload.status.value,
                    upload.progress, upload.uploaded_bytes, upload.total_bytes,
                    upload.speed, upload.url, upload.error, upload.upload_id,
                    _dt(upload.started_at), _dt(upload.completed_at),
                ),
            )

    def get(self, task_id: str) -> Task | None:
        row = self.db.connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        uploads = self.db.connection.execute(
            "SELECT * FROM uploads WHERE task_id = ? ORDER BY provider_id", (task_id,)
        ).fetchall()
        return self._from_row(row, uploads)

    def list(self, limit: int = 100) -> list[Task]:
        if limit < 1:
            raise ValueError("Limit must be at least 1")
        rows = self.db.connection.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, task_id: str) -> bool:
        cursor = self.db.connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.db.connection.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _from_row(row, uploads=None) -> Task:
        if uploads is None:
            uploads = []
        return Task(
            id=row["id"], source_url=row["source_url"],
            original_filename=row["original_filename"], custom_filename=row["custom_filename"],
            final_filename=row["final_filename"], status=TaskStatus(row["status"]),
            selected_providers=json.loads(row["selected_providers"]), file_path=row["file_path"],
            file_size=row["file_size"], downloaded_bytes=row["downloaded_bytes"],
            download_speed=row["download_speed"], download_progress=row["download_progress"],
            download_eta=row["download_eta"], file_sha256=row["file_sha256"],
            created_at=_parse_dt(row["created_at"]), started_at=_parse_dt(row["started_at"]),
            completed_at=_parse_dt(row["completed_at"]), error=row["error"],
            uploads=[UploadResult(
                task_id=u["task_id"], provider_id=u["provider_id"], status=UploadStatus(u["status"]),
                progress=u["progress"], uploaded_bytes=u["uploaded_bytes"], total_bytes=u["total_bytes"],
                speed=u["speed"], url=u["url"], error=u["error"], upload_id=u["upload_id"],
                started_at=_parse_dt(u["started_at"]), completed_at=_parse_dt(u["completed_at"]),
            ) for u in uploads],
        )
