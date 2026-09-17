"""Tests for the SQLite persistence layer."""

import tempfile
import unittest
from pathlib import Path

from core.database import Database, TaskRepository
from core.models import Task, TaskStatus, UploadResult, UploadStatus


class DatabaseTests(unittest.TestCase):
    def test_task_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "test.db")
            repo = TaskRepository(db)
            task = Task(
                "task-1",
                "https://example.test/video.mp4",
                custom_filename="my-video.mp4",
                selected_providers=["gofile", "pixeldrain"],
                status=TaskStatus.DOWNLOADING,
                download_progress=42.5,
            )
            task.uploads.append(
                UploadResult("task-1", "gofile", UploadStatus.COMPLETED, 100, url="https://gofile.test/x")
            )
            repo.save(task)

            loaded = repo.get("task-1")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.status, TaskStatus.DOWNLOADING)
            self.assertEqual(loaded.custom_filename, "my-video.mp4")
            self.assertEqual(loaded.selected_providers, ["gofile", "pixeldrain"])
            self.assertEqual(len(loaded.uploads), 1)
            self.assertEqual(loaded.uploads[0].url, "https://gofile.test/x")
            db.close()

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "test.db")
            repo = TaskRepository(db)
            repo.save(Task("task-1", "https://example.test/video"))
            self.assertTrue(repo.delete("task-1"))
            self.assertIsNone(repo.get("task-1"))
            self.assertFalse(repo.delete("missing"))
            db.close()


if __name__ == "__main__":
    unittest.main()
