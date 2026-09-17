"""Tests for cLOADER core models."""

import unittest

from core.models import (
    FileInfo,
    ProviderCapabilities,
    ProviderInfo,
    ProviderKind,
    Task,
    TaskStatus,
    UploadResult,
    UploadStatus,
)


class ModelTests(unittest.TestCase):
    def test_file_info(self):
        file_info = FileInfo("/tmp/video.mp4", "video.mp4", 1024, "video/mp4")
        self.assertEqual(file_info.filename, "video.mp4")
        self.assertEqual(file_info.size, 1024)

    def test_provider_info(self):
        provider = ProviderInfo(
            "GoFile", "GoFile", ProviderKind.FILE,
            capabilities=ProviderCapabilities(resume=True),
        )
        self.assertEqual(provider.id, "gofile")
        self.assertTrue(provider.capabilities.resume)

    def test_upload_result(self):
        result = UploadResult("task-1", "Pixeldrain", UploadStatus.COMPLETED, 100.0, url="https://example.test/file")
        self.assertEqual(result.provider_id, "pixeldrain")
        self.assertEqual(result.status, UploadStatus.COMPLETED)

    def test_task_defaults_and_providers(self):
        task = Task("task-1", "https://example.test/video", selected_providers=["GoFile", "Pixeldrain"])
        self.assertEqual(task.status, TaskStatus.QUEUED)
        self.assertEqual(task.selected_providers, ["gofile", "pixeldrain"])
        self.assertEqual(task.provider_count, 2)
        self.assertEqual(task.successful_uploads, [])

    def test_invalid_progress_is_rejected(self):
        with self.assertRaises(ValueError):
            UploadResult("task-1", "gofile", progress=101)
        with self.assertRaises(ValueError):
            Task("task-1", "https://example.test/video", download_progress=-1)


if __name__ == "__main__":
    unittest.main()
