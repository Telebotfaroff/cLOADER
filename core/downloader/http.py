"""High-throughput HTTP downloader."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ProgressCallback = Callable[[int, int | None, float], Awaitable[None] | None]


class HTTPDownloader:
    """Stream an HTTP/HTTPS resource to disk with progress reporting.

    The downloader deliberately avoids an artificial bandwidth limit. The
    effective speed is determined by the source server, network, CPU, and disk.
    """

    def __init__(self, chunk_size: int = 1024 * 1024, timeout: int = 60) -> None:
        if chunk_size < 64 * 1024:
            raise ValueError("chunk_size must be at least 64 KiB")
        self.chunk_size = chunk_size
        self.timeout = timeout

    async def download(
        self,
        url: str,
        destination: str | os.PathLike[str],
        *,
        progress_callback: ProgressCallback | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, int | None]:
        """Download *url* into *destination*.

        Network I/O uses a worker thread so the async application remains
        responsive while the file is being written.
        """
        return await asyncio.to_thread(
            self._download_sync,
            url,
            destination,
            progress_callback,
            headers or {},
        )

    def _download_sync(
        self,
        url: str,
        destination: str | os.PathLike[str],
        progress_callback: ProgressCallback | None,
        headers: dict[str, str],
    ) -> tuple[int, int | None]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only HTTP and HTTPS URLs are supported")

        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        request_headers = {"User-Agent": "cLOADER/1.0", "Accept-Encoding": "identity"}
        request_headers.update(headers)
        request = Request(url, headers=request_headers)

        downloaded = 0
        started = time.monotonic()
        last_update = started

        with urlopen(request, timeout=self.timeout) as response, path.open("wb") as output:
            content_length = response.headers.get("Content-Length")
            total = int(content_length) if content_length and content_length.isdigit() else None

            while True:
                chunk = response.read(self.chunk_size)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)

                now = time.monotonic()
                if progress_callback and (now - last_update >= 0.25 or (total and downloaded >= total)):
                    speed = downloaded / max(now - started, 0.001)
                    self._notify(progress_callback, downloaded, total, speed)
                    last_update = now

        if progress_callback:
            speed = downloaded / max(time.monotonic() - started, 0.001)
            self._notify(progress_callback, downloaded, total, speed)

        return downloaded, total

    @staticmethod
    def _notify(callback: ProgressCallback, downloaded: int, total: int | None, speed: float) -> None:
        result = callback(downloaded, total, speed)
        if asyncio.iscoroutine(result):
            # The sync worker cannot safely await the application's loop.
            # Callers using async callbacks should use DownloadManager, which
            # bridges progress updates back onto the event loop.
            result.close()
