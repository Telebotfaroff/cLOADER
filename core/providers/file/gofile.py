"""GoFile upload provider.

API verified against GoFile's official API documentation:
https://gofile.io/api
"""

from __future__ import annotations

import asyncio
import http.client
import json
import mimetypes
import os
import secrets
import ssl
import time
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlparse

from core.providers.base import ProgressCallback, ProviderUpload, UploadProvider


class GofileProvider(UploadProvider):
    """Upload files to GoFile using its multipart upload endpoint."""

    id = "gofile"
    name = "GoFile"
    upload_host = "upload.gofile.io"
    upload_path = "/uploadfile"

    def __init__(
        self,
        token: str | None = None,
        *,
        folder_id: str | None = None,
        timeout: int = 120,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        self.token = token
        self.folder_id = folder_id
        self.timeout = timeout
        self.chunk_size = max(256 * 1024, chunk_size)

    async def upload(
        self,
        file_path: str | Path,
        filename: str,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> ProviderUpload:
        return await asyncio.to_thread(
            self._upload_sync,
            Path(file_path),
            filename,
            progress_callback,
        )

    def _upload_sync(
        self,
        file_path: Path,
        filename: str,
        progress_callback: ProgressCallback | None,
    ) -> ProviderUpload:
        if not file_path.is_file():
            raise FileNotFoundError(file_path)

        total = file_path.stat().st_size
        boundary = f"----cLOADER{secrets.token_hex(16)}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        fields: list[tuple[str, str]] = []
        if self.folder_id:
            fields.append(("folderId", self.folder_id))
        if self.token:
            fields.append(("token", self.token))

        body_prefix = self._multipart_prefix(boundary, fields, filename, content_type)
        body_suffix = f"\r\n--{boundary}--\r\n".encode()
        content_length = len(body_prefix) + total + len(body_suffix)

        conn = http.client.HTTPSConnection(self.upload_host, timeout=self.timeout)
        started = time.monotonic()
        uploaded = 0
        try:
            conn.putrequest("POST", self.upload_path)
            conn.putheader("Host", self.upload_host)
            conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
            conn.putheader("Content-Length", str(content_length))
            conn.putheader("User-Agent", "cLOADER/1.0")
            conn.endheaders()

            conn.send(body_prefix)
            with file_path.open("rb") as source:
                while True:
                    chunk = source.read(self.chunk_size)
                    if not chunk:
                        break
                    conn.send(chunk)
                    uploaded += len(chunk)
                    if progress_callback:
                        speed = uploaded / max(time.monotonic() - started, 0.001)
                        self._notify(progress_callback, uploaded, total, speed)

            conn.send(body_suffix)
            response = conn.getresponse()
            raw = response.read()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"GoFile HTTP {response.status}: {raw[:500].decode(errors='replace')}")

            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError("GoFile returned invalid JSON") from exc

            if payload.get("status") != "ok":
                raise RuntimeError(f"GoFile upload failed: {payload.get('status')}")

            data = payload.get("data") or {}
            url = data.get("downloadPage")
            if not url:
                raise RuntimeError("GoFile response did not contain downloadPage")

            return ProviderUpload(url=str(url), upload_id=str(data.get("id")) if data.get("id") else None)
        finally:
            conn.close()

    @staticmethod
    def _multipart_prefix(
        boundary: str,
        fields: list[tuple[str, str]],
        filename: str,
        content_type: str,
    ) -> bytes:
        parts: list[bytes] = []
        for name, value in fields:
            parts.append(
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n".encode()
            )
        parts.append(
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename.replace(chr(34), '_')}\"\r\n"
            f"Content-Type: {content_type}\r\n\r\n".encode()
        )
        return b"".join(parts)

    @staticmethod
    def _notify(callback: ProgressCallback, uploaded: int, total: int, speed: float) -> None:
        result = callback(uploaded, total, speed)
        if asyncio.iscoroutine(result):
            result.close()
