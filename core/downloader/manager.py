"""Download orchestration and progress reporting."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from .http import HTTPDownloader


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    downloaded_bytes: int
    total_bytes: int | None
    speed: float
    progress: float
    eta: float | None


ProgressHandler = Callable[[DownloadProgress], Awaitable[None] | None]


class DownloadManager:
    """Manage temporary downloads without imposing a bandwidth ceiling."""

    def __init__(self, download_dir: str = "downloads", chunk_size: int = 1024 * 1024) -> None:
        self.download_dir = Path(download_dir)
        self.downloader = HTTPDownloader(chunk_size=chunk_size)

    async def download(
        self,
        url: str,
        filename: str | None = None,
        *,
        progress_handler: ProgressHandler | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[Path, int, int | None]:
        """Download a URL to a temporary file and return its path and sizes."""
        self.download_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename or f"download-{uuid.uuid4().hex}").name
        destination = self.download_dir / safe_name
        loop = asyncio.get_running_loop()

        def on_progress(downloaded: int, total: int | None, speed: float) -> None:
            percent = (downloaded / total * 100) if total else 0.0
            eta = ((total - downloaded) / speed) if total and speed > 0 else None
            event = DownloadProgress(downloaded, total, speed, percent, eta)
            if progress_handler:
                result = progress_handler(event)
                if asyncio.iscoroutine(result):
                    asyncio.run_coroutine_threadsafe(result, loop)

        started = time.monotonic()
        downloaded, total = await self.downloader.download(
            url,
            destination,
            progress_callback=on_progress,
            headers=headers,
        )
        if progress_handler:
            speed = downloaded / max(time.monotonic() - started, 0.001)
            final = DownloadProgress(downloaded, total, speed, 100.0 if total else 0.0, 0.0 if total else None)
            result = progress_handler(final)
            if asyncio.iscoroutine(result):
                await result

        return destination, downloaded, total
