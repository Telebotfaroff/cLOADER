"""Provider upload orchestration with retries and cleanup safety."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.events import Event, EventBus, EventType
from core.models import Task, TaskStatus, UploadResult, UploadStatus
from core.providers.base import ProviderUpload, UploadProvider


@dataclass(frozen=True, slots=True)
class UploadSummary:
    results: list[UploadResult]
    all_succeeded: bool
    cleaned_up: bool


class UploadManager:
    """Upload a local file to selected providers concurrently with retries."""

    def __init__(self, providers: dict[str, UploadProvider], *, event_bus: EventBus | None = None,
                 max_concurrency: int = 2, max_retries: int = 2, retry_delay: float = 2.0) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self.providers = {key.lower(): value for key, value in providers.items()}
        self.event_bus = event_bus
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries
        self.retry_delay = max(0.0, retry_delay)

    async def upload_task(self, task: Task) -> UploadSummary:
        if not task.file_path:
            raise ValueError("Task has no local file path")
        file_path = Path(task.file_path)
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        selected = list(dict.fromkeys(p.lower() for p in task.selected_providers))
        missing = [p for p in selected if p not in self.providers]
        if missing:
            raise ValueError(f"Unknown providers: {', '.join(missing)}")
        previous = {r.provider_id: r for r in task.uploads if r.status is UploadStatus.COMPLETED and r.url}
        pending = [p for p in selected if p not in previous]
        results = list(previous.values())
        if pending:
            semaphore = asyncio.Semaphore(self.max_concurrency)
            fresh = await asyncio.gather(*(self._upload_one(task, p, semaphore) for p in pending))
            results.extend(fresh)
        results.sort(key=lambda r: selected.index(r.provider_id))
        task.uploads = results
        all_succeeded = len(results) == len(selected) and all(r.status is UploadStatus.COMPLETED for r in results)
        cleaned_up = False
        if all_succeeded:
            file_path.unlink(missing_ok=True)
            cleaned_up = not file_path.exists()
            if cleaned_up:
                task.file_path = None
                task.status = TaskStatus.COMPLETED
        return UploadSummary(results, all_succeeded, cleaned_up)

    async def _upload_one(self, task: Task, provider_id: str, semaphore: asyncio.Semaphore) -> UploadResult:
        provider = self.providers[provider_id]
        result = UploadResult(task.id, provider_id, total_bytes=task.file_size)
        async with semaphore:
            await self._publish(EventType.UPLOAD_STARTED, task.id, {"provider": provider_id})
            for attempt in range(self.max_retries + 1):
                result.status = UploadStatus.RETRYING if attempt else UploadStatus.UPLOADING
                try:
                    uploaded = await provider.upload(
                        task.file_path,
                        task.final_filename or task.custom_filename or task.original_filename or "download",
                        progress_callback=self._progress_callback(task.id, provider_id, result),
                    )
                    self._apply_success(result, uploaded)
                    await self._publish(EventType.UPLOAD_COMPLETED, task.id,
                                       {"provider": provider_id, "url": result.url})
                    return result
                except Exception as exc:
                    result.error = str(exc) or exc.__class__.__name__
                    if attempt < self.max_retries:
                        await self._publish(EventType.UPLOAD_FAILED, task.id,
                                           {"provider": provider_id, "error": result.error, "retrying": True})
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        result.status = UploadStatus.FAILED
                        await self._publish(EventType.UPLOAD_FAILED, task.id,
                                           {"provider": provider_id, "error": result.error, "retrying": False})
        return result

    @staticmethod
    def _apply_success(result: UploadResult, uploaded: ProviderUpload) -> None:
        result.status = UploadStatus.COMPLETED
        result.progress = 100.0
        result.uploaded_bytes = result.total_bytes
        result.url = uploaded.url
        result.upload_id = uploaded.upload_id
        result.error = None

    def _progress_callback(self, task_id: str, provider_id: str, result: UploadResult) -> Callable[[int, int, float], None]:
        loop = asyncio.get_running_loop()

        def callback(uploaded: int, total: int, speed: float) -> None:
            result.uploaded_bytes = max(0, uploaded)
            result.total_bytes = max(0, total)
            result.speed = max(0.0, speed)
            result.progress = (uploaded / total * 100.0) if total else 0.0
            if self.event_bus:
                asyncio.run_coroutine_threadsafe(self._publish(EventType.UPLOAD_PROGRESS, task_id, {
                    "provider": provider_id, "uploaded_bytes": uploaded, "total_bytes": total,
                    "progress": result.progress, "speed": result.speed,
                }), loop)
        return callback

    async def _publish(self, event_type: EventType, task_id: str, data: dict) -> None:
        if self.event_bus:
            await self.event_bus.publish(Event(event_type, task_id, data))
