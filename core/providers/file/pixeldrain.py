"""Pixeldrain upload provider."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from core.providers.base import ProgressCallback, ProviderUpload, UploadProvider


class PixeldrainProvider(UploadProvider):
    id = "pixeldrain"
    name = "Pixeldrain"

    def __init__(self, *, api_key: str | None = None, timeout: float = 120.0) -> None:
        self.api_key = api_key or os.getenv("PIXELDRAIN_API_KEY")
        self.timeout = timeout

    async def upload(self, file_path: str | Path, filename: str, *, progress_callback: ProgressCallback | None = None) -> ProviderUpload:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        return await asyncio.to_thread(self._upload_sync, path, filename, progress_callback)

    def _upload_sync(self, path: Path, filename: str, progress_callback: ProgressCallback | None) -> ProviderUpload:
        total = path.stat().st_size
        url = "https://pixeldrain.com/api/file/" + quote(filename, safe="")
        headers = {"Content-Type": "application/octet-stream", "Content-Length": str(total)}
        if self.api_key:
            token = base64.b64encode(f":{self.api_key}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        started = time.monotonic()

        class UploadBody:
            def __init__(self, source: Path, size: int, callback: ProgressCallback | None) -> None:
                self.source, self.size, self.callback = source, size, callback
                self.file = source.open("rb")
                self.sent = 0

            def read(self, size: int = -1) -> bytes:
                data = self.file.read(1024 * 1024 if size == -1 else min(size, 1024 * 1024))
                if data:
                    self.sent += len(data)
                    if self.callback:
                        speed = self.sent / max(time.monotonic() - started, 0.001)
                        self.callback(self.sent, self.size, speed)
                else:
                    self.file.close()
                return data

        body = UploadBody(path, total, progress_callback)
        request = Request(url, data=body, headers=headers, method="PUT")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Pixeldrain HTTP {exc.code}: {body_text[:500]}") from exc
        except URLError as exc:
            raise RuntimeError(f"Pixeldrain connection failed: {exc.reason}") from exc
        finally:
            if not body.file.closed:
                body.file.close()
        if not payload.get("success", False):
            raise RuntimeError(str(payload.get("value") or payload))
        file_id = payload.get("id")
        if not file_id:
            raise RuntimeError(f"Pixeldrain response missing file id: {payload}")
        return ProviderUpload(url=f"https://pixeldrain.com/u/{file_id}", upload_id=str(file_id))
