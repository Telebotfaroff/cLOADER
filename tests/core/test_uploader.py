"""Tests for upload orchestration, retries, and cleanup safety."""

import tempfile
import unittest
from pathlib import Path

from core.events import EventBus
from core.models import Task, UploadStatus
from core.providers.base import ProviderUpload, UploadProvider
from core.uploader.manager import UploadManager


class FakeProvider(UploadProvider):
    def __init__(self, provider_id, failures=0):
        self.id = provider_id
        self.name = provider_id
        self.failures = failures
        self.calls = 0

    async def upload(self, file_path, filename, *, progress_callback=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("simulated upload failure")
        total = Path(file_path).stat().st_size
        if progress_callback:
            await progress_callback(total, total, 100.0)
        return ProviderUpload(f"https://example.test/{self.id}/result", f"{self.id}-1")


class UploadManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_then_success_cleans_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(b"payload")
            provider = FakeProvider("test", failures=1)
            task = Task("retry", "https://example.test/source", final_filename="video.mp4",
                        selected_providers=["test"], file_path=str(path), file_size=7)
            manager = UploadManager({"test": provider}, event_bus=EventBus(), max_retries=1, retry_delay=0)
            summary = await manager.upload_task(task)
            self.assertTrue(summary.all_succeeded)
            self.assertTrue(summary.cleaned_up)
            self.assertFalse(path.exists())
            self.assertEqual(provider.calls, 2)
            self.assertEqual(summary.results[0].status, UploadStatus.COMPLETED)

    async def test_one_failure_keeps_file_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(b"payload")
            good = FakeProvider("good")
            bad = FakeProvider("bad", failures=10)
            task = Task("partial", "https://example.test/source", final_filename="video.mp4",
                        selected_providers=["good", "bad"], file_path=str(path), file_size=7)
            manager = UploadManager({"good": good, "bad": bad}, event_bus=EventBus(), max_retries=1, retry_delay=0)
            summary = await manager.upload_task(task)
            self.assertFalse(summary.all_succeeded)
            self.assertFalse(summary.cleaned_up)
            self.assertTrue(path.exists())
            self.assertEqual(summary.results[0].status, UploadStatus.COMPLETED)
            self.assertEqual(summary.results[1].status, UploadStatus.FAILED)

    async def test_unknown_provider_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.bin"
            path.write_bytes(b"x")
            task = Task("unknown", "https://example.test/source", selected_providers=["missing"],
                        file_path=str(path), file_size=1)
            manager = UploadManager({}, max_retries=0)
            with self.assertRaises(ValueError):
                await manager.upload_task(task)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
