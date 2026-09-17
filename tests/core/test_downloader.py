"""Unit tests for downloader helpers."""

import unittest
from unittest.mock import patch

from core.downloader.media import filename_from_url
from core.downloader.manager import DownloadProgress


class DownloaderTests(unittest.TestCase):
    def test_filename_from_url(self):
        self.assertEqual(filename_from_url("https://example.test/path/video%20one.mp4"), "video one.mp4")
        self.assertEqual(filename_from_url("https://example.test/"), "download")

    def test_progress_values(self):
        progress = DownloadProgress(5_000_000, 10_000_000, 2_000_000, 50.0, 2.5)
        self.assertEqual(progress.downloaded_bytes, 5_000_000)
        self.assertEqual(progress.progress, 50.0)
        self.assertEqual(progress.eta, 2.5)

    def test_downloader_has_no_artificial_bandwidth_cap(self):
        from core.downloader.http import HTTPDownloader
        downloader = HTTPDownloader(chunk_size=1024 * 1024)
        self.assertEqual(downloader.chunk_size, 1024 * 1024)
        self.assertFalse(hasattr(downloader, "max_speed"))


if __name__ == "__main__":
    unittest.main()
