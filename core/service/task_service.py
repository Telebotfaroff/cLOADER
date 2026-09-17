"""Application-level orchestration for download/upload tasks."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

from core.database.repositories import TaskRepository
from core.events import Event, EventBus, EventType
from core.models import Task, TaskStatus
from core.downloader.manager import DownloadManager
from core.uploader.manager import UploadManager


class TaskService:
    """Runs the complete URL -> download -> upload -> cleanup workflow."""

    def __init__(
        self,
        repository: TaskRepository,
        downloader: DownloadManager,
        uploader: UploadManager,
        event_bus: EventBus,
    ) -> None:
        self.repository = repository
        self.downloader = downloader
        self.uploader = uploader
        self.event_bus = event_bus
        self._jobs: dict[str, asyncio.Task[None]] = {}

    async def create_and_start(self, task: Task) -> Task:
        self.repository.save_task(task)
        await self.event_bus.publish(Event(EventType.TASK_CREATED, task.id, {"url": task.source_url}))
        self._jobs[task.id] = asyncio.create_task(self.run(task))
        return task

    async def run(self, task: Task) -> None:
        try:
            task.status = TaskStatus.DOWNLOADING
            self.repository.save_task(task)
            await self.event_bus.publish(Event(EventType.DOWNLOAD_STARTED, task.id, {"url": task.source_url}))

            def progress(value) -> None:
                task.downloaded_bytes = value.downloaded_bytes
                task.download_speed = value.speed
                task.download_progress = value.progress
                task.download_eta = value.eta
                self.repository.save_task(task)
                asyncio.create_task(self.event_bus.publish(Event(
                    EventType.DOWNLOAD_PROGRESS,
                    task.id,
                    {
                        "downloaded_bytes": value.downloaded_bytes,
                        "total_bytes": value.total_bytes,
                        "progress": value.progress,
                        "speed": value.speed,
                        "eta": value.eta,
                    },
                )))

            filename = task.final_filename or task.custom_filename or task.original_filename
            path, size, total = await self.downloader.download(task.source_url, filename, progress_handler=progress)
            task.file_path = str(path)
            task.file_size = total or size
            task.downloaded_bytes = size
            task.status = TaskStatus.DOWNLOADED
            if not task.original_filename:
                task.original_filename = path.name
            if not task.final_filename:
                task.final_filename = task.custom_filename or path.name
            self.repository.save_task(task)
            await self.event_bus.publish(Event(EventType.DOWNLOAD_COMPLETED, task.id, {"size": size}))

            task.status = TaskStatus.UPLOADING
            self.repository.save_task(task)
            summary = await self.uploader.upload_task(task)
            for result in summary.results:
                self.repository.save_upload_result(result)
            if summary.all_succeeded:
                task.status = TaskStatus.COMPLETED
                task.file_path = None
                await self.event_bus.publish(Event(EventType.TASK_COMPLETED, task.id, {
                    "uploads": [{"provider": r.provider_id, "url": r.url} for r in summary.results]
                }))
            else:
                task.status = TaskStatus.FAILED
                task.error = "One or more provider uploads failed; temporary file retained for retry."
                await self.event_bus.publish(Event(EventType.TASK_FAILED, task.id, {"error": task.error}))
            self.repository.save_task(task)
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            self.repository.save_task(task)
            raise
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc) or exc.__class__.__name__
            self.repository.save_task(task)
            await self.event_bus.publish(Event(EventType.TASK_FAILED, task.id, {"error": task.error}))
        finally:
            self._jobs.pop(task.id, None)

    async def cancel(self, task_id: str) -> bool:
        job = self._jobs.get(task_id)
        if job is None:
            return False
        job.cancel()
        return True

    def get_job(self, task_id: str) -> asyncio.Task[None] | None:
        return self._jobs.get(task_id)
