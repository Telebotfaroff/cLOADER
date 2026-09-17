"""GoFile upload provider."""

from __future__ import annotations

import asyncio
import http.client
import json
import mimetypes
import secrets
import time
from pathlib import Path

from core.providers.base import ProgressCallback, ProviderUpload, UploadProvider


class GofileProvider(UploadProvider):
    id = "gofile"
    name = "GoFile"
    upload_host = "upload.gofile.io"
    upload_path = "/uploadfile"

    def __init__(self, token: str | None = None, *, folder_id: str | None = None,
                 timeout: int = 120, chunk_size: int = 1024 * 1024) -> None:
        self.token = token
        self.folder_id = folder_id
        self.timeout = timeout
        self.chunk_size = max(256 * 1024, chunk_size)

    async def upload(self, file_path: str | Path, filename: str, *, progress_callback: ProgressCallback | None = None) -> ProviderUpload:
        return await asyncio.to_thread(self._upload_sync, Path(file_path), filename, progress_callback)

    def _upload_sync(self, file_path: Path, filename: str, progress_callback: ProgressCallback | None) -> ProviderUpload:
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        total = file_path.stat().st_size
        boundary = f"----cLOADER{secrets.token_hex(16)}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        fields = [("folderId", self.folder_id)] if self.folder_id else []
        if self.token:
            fields.append(("token", self.token))
        prefix = self._multipart_prefix(boundary, fields, filename, content_type)
        suffix = f"\r\n--{boundary}--\r\n".encode()
        conn = http.client.HTTPSConnection(self.upload_host, timeout=self.timeout)
        started = time.monotonic(); uploaded = 0
        try:
            conn.putrequest("POST", self.upload_path)
            conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
            conn.putheader("Content-Length", str(len(prefix) + total + len(suffix)))
            conn.putheader("User-Agent", "cLOADER/1.0")
            conn.endheaders(); conn.send(prefix)
            with file_path.open("rb") as source:
                while chunk := source.read(self.chunk_size):
                    conn.send(chunk); uploaded += len(chunk)
                    if progress_callback:
                        result = progress_callback(uploaded, total, uploaded / max(time.monotonic() - started, .001))
                        if asyncio.iscoroutine(result):
                            asyncio.run(result)
            conn.send(suffix)
            response = conn.getresponse(); raw = response.read()
            if not 200 <= response.status < 300:
                raise RuntimeError(f"GoFile HTTP {response.status}: {raw[:500].decode(errors='replace')}")
            payload = json.loads(raw.decode("utf-8"))
            if payload.get("status") != "ok":
                raise RuntimeError(f"GoFile upload failed: {payload.get('status')}")
            data = payload.get("data") or {}; url = data.get("downloadPage")
            if not url:
                raise RuntimeError("GoFile response did not contain downloadPage")
            return ProviderUpload(str(url), str(data.get("id")) if data.get("id") else None)
        finally:
            conn.close()

    @staticmethod
    def _multipart_prefix(boundary: str, fields: list[tuple[str, str]], filename: str, content_type: str) -> bytes:
        parts = []
        for name, value in fields:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
        safe = filename.replace('"', '_')
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{safe}\"\r\nContent-Type: {content_type}\r\n\r\n".encode())
        return b"".join(parts)
