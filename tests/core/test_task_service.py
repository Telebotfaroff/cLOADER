"""Tests for the complete task orchestration workflow."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from core.database.database import Database
from core.database.repositories import TaskRepository
from core.events import EventBus
from core.models import Task, TaskStatus, UploadResult, UploadStatus
from core.service.task_service import TaskService


class FakeDownloader:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    async def download(self, url, filename=None, *, progress_handler=None, headers=None):
        path = self.directory / (filename or "download.bin")
        path.write_bytes(b"test payload")
        if progress_handler:
            progress_handler(type("Progress", (), {
                "downloaded_bytes": 12, "total_bytes": 12, "speed": 100.0,
                "progress": 100.0, "eta": 0.0,
            })())
        return path, 12, 12


class FakeUploader:
    def __init__(self, succeed=True, fail_first=False):
        self.succeed = succeed
        self.fail_first = fail_first
        self.calls = {}

    async def upload_task(self, task):
        results = []
        for provider in task.selected_providers:
            count = self.calls.get(provider, 0)
            self.calls[provider] = count + 1
            should_fail = not self.succeed or (self.fail_first and count == 0)
            results.append(UploadResult(
                task.id, provider,
                status=UploadStatus.FAILED if should_fail else UploadStatus.COMPLETED,
                progress=0 if should_fail else 100,
                total_bytes=task.file_size,
                url=None if should_fail else f"https://example.test/{provider}/{task.id}",
                error="simulated failure" if should_fail else None,
            ))
        all_succeeded = all(r.status is UploadStatus.COMPLETED for r in results)
        if all_succeeded:
            Path(task.file_path).unlink(missing_ok=True)
        return type("Summary", (), {
            "results": results,
            "all_succeeded": all_succeeded,
            "cleaned_up": all_succeeded,
        })()


class TaskServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_workflow_cleans_up_and_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(str(Path(tmp) / "data"))
            repo = TaskRepository(db)
            service = TaskService(repo, FakeDownloader(Path(tmp)), FakeUploader(), EventBus())
            task = Task("task-success", "https://example.test/file", selected_providers=["gofile", "pixeldrain"])
            await service.create_and_start(task)
            await service.get_job(task.id)
            while service.get_job(task.id):
                await asyncio.sleep(0.01)
            saved = repo.get(task.id)
            self.assertEqual(saved.status, TaskStatus.COMPLETED)
            self.assertIsNone(saved.file_path)
            self.assertEqual(len(saved.uploads), 2)
            self.assertTrue(all(u.status is UploadStatus.COMPLETED for u in saved.uploads))

    async def test_failed_upload_retains_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(str(Path(tmp) / "data"))
            repo = TaskRepository(db)
            service = TaskService(repo, FakeDownloader(Path(tmp)), FakeUploader(succeed=False), EventBus())
            task = Task("task-fail", "https://example.test/file", selected_providers=["gofile"])
            await service.create_and_start(task)
            while service.get_job(task.id):
                await asyncio.sleep(0.01)
            saved = repo.get(task.id)
            self.assertEqual(saved.status, TaskStatus.FAILED)
            self.assertIsNotNone(saved.file_path)
            self.assertTrue(Path(saved.file_path).exists())

    async def test_repository_method_is_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(str(Path(tmp) / "data"))
            repo = TaskRepository(db)
            service = TaskService(repo, FakeDownloader(Path(tmp)), FakeUploader(), EventBus())
            task = Task("task-save", "https://example.test/file", selected_providers=["gofile"])
            await service.create_and_start(task)
            while service.get_job(task.id):
                await asyncio.sleep(0.01)
            self.assertIsNotNone(repo.get(task.id))


if __name__ == "__main__":
    unittest.main()
