"""Pixeldrain upload provider.

Uses Pixeldrain's file PUT endpoint. The API key is optional for the public
endpoint and can be supplied through PIXELDRAIN_API_KEY when configured.
"""

from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.providers.base import ProgressCallback, ProviderUpload, UploadProvider


class PixeldrainProvider(UploadProvider):
    id = "pixeldrain"
    name = "Pixeldrain"

    def __init__(self, *, api_key: str | None = None, timeout: float = 120.0) -> None:
        self.api_key = api_key or os.getenv("PIXELDRAIN_API_KEY")
        self.timeout = timeout

    async def upload(
        self,
        file_path: str | Path,
        filename: str,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> ProviderUpload:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(path)

        return await asyncio.to_thread(
            self._upload_sync, path, filename, progress_callback
        )

    def _upload_sync(
        self,
        path: Path,
        filename: str,
        progress_callback: ProgressCallback | None,
    ) -> ProviderUpload:
        total = path.stat().st_size
        url = "https://pixeldrain.com/api/file/" + filename
        headers: dict[str, str] = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(total),
        }
        if self.api_key:
            token = base64.b64encode(f":{self.api_key}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"

        class UploadBody:
            def __init__(self, source: Path, size: int, callback: Any) -> None:
                self.source = source
                self.size = size
                self.callback = callback
                self.sent = 0
                self.chunk = 1024 * 1024

            def read(self, size: int = -1) -> bytes:
                if not hasattr(self, "file"):
                    self.file = self.source.open("rb")
                data = self.file.read(self.chunk if size == -1 else min(size, self.chunk))
                if data:
                    self.sent += len(data)
                    if self.callback:
                        result = self.callback(self.sent, self.size, 0.0)
                        if asyncio.iscoroutine(result):
                            result.close()
                else:
                    self.file.close()
                return data

        request = Request(url, data=UploadBody(path, total, progress_callback), headers=headers, method="PUT")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                import json
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Pixeldrain HTTP {exc.code}: {body[:500]}") from exc
        except URLError as exc:
            raise RuntimeError(f"Pixeldrain connection failed: {exc.reason}") from exc

        if not payload.get("success", False):
            raise RuntimeError(str(payload.get("value") or payload))
        file_id = payload.get("id")
        if not file_id:
            raise RuntimeError(f"Pixeldrain response missing file id: {payload}")
        return ProviderUpload(
            url=f"https://pixeldrain.com/u/{file_id}",
            upload_id=str(file_id),
        )
