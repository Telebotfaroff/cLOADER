"""Application-level orchestration for download/upload tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from core.database.repositories import TaskRepository
from core.events import Event, EventBus, EventType
from core.models import Task, TaskStatus
from core.downloader.manager import DownloadManager
from core.uploader.manager import UploadManager


class TaskService:
    """Runs the complete URL -> download -> upload -> cleanup workflow."""

    def __init__(self, repository: TaskRepository, downloader: DownloadManager, uploader: UploadManager, event_bus: EventBus) -> None:
        self.repository = repository
        self.downloader = downloader
        self.uploader = uploader
        self.event_bus = event_bus
        self._jobs: dict[str, asyncio.Task[None]] = {}

    async def create_and_start(self, task: Task) -> Task:
        self.repository.save(task)
        await self.event_bus.publish(Event(EventType.TASK_CREATED, task.id, {"url": task.source_url}))
        self._jobs[task.id] = asyncio.create_task(self.run(task))
        return task

    async def run(self, task: Task) -> None:
        try:
            task.status = TaskStatus.DOWNLOADING
            task.started_at = task.started_at or datetime.now(timezone.utc)
            self.repository.save(task)
            await self.event_bus.publish(Event(EventType.DOWNLOAD_STARTED, task.id, {"url": task.source_url}))

            def progress(value) -> None:
                task.downloaded_bytes = value.downloaded_bytes
                task.download_speed = value.speed
                task.download_progress = value.progress
                task.download_eta = value.eta
                self.repository.save(task)
                asyncio.create_task(self.event_bus.publish(Event(EventType.DOWNLOAD_PROGRESS, task.id, {
                    "downloaded_bytes": value.downloaded_bytes, "total_bytes": value.total_bytes,
                    "progress": value.progress, "speed": value.speed, "eta": value.eta,
                })))

            filename = task.final_filename or task.custom_filename or task.original_filename
            path, size, total = await self.downloader.download(task.source_url, filename, progress_handler=progress)
            task.file_path = str(path)
            task.file_size = total or size
            task.downloaded_bytes = size
            task.download_progress = 100.0 if total else task.download_progress
            task.status = TaskStatus.DOWNLOADED
            if not task.original_filename:
                task.original_filename = path.name
            if not task.final_filename:
                task.final_filename = task.custom_filename or path.name
            self.repository.save(task)
            await self.event_bus.publish(Event(EventType.DOWNLOAD_COMPLETED, task.id, {"size": size}))
            await self._upload_existing_file(task)
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            self.repository.save(task)
            raise
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc) or exc.__class__.__name__
            self.repository.save(task)
            await self.event_bus.publish(Event(EventType.TASK_FAILED, task.id, {"error": task.error}))
        finally:
            self._jobs.pop(task.id, None)

    async def _upload_existing_file(self, task: Task) -> bool:
        task.status = TaskStatus.UPLOADING
        task.error = None
        self.repository.save(task)
        summary = await self.uploader.upload_task(task)
        task.uploads = summary.results
        if summary.all_succeeded:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.file_path = None
            task.error = None
            await self.event_bus.publish(Event(EventType.TASK_COMPLETED, task.id, {
                "uploads": [{"provider": r.provider_id, "url": r.url} for r in summary.results]
            }))
        else:
            task.status = TaskStatus.FAILED
            task.error = "One or more provider uploads failed; temporary file retained for retry."
            await self.event_bus.publish(Event(EventType.TASK_FAILED, task.id, {"error": task.error}))
        self.repository.save(task)
        return summary.all_succeeded

    async def retry_uploads(self, task: Task) -> bool:
        """Retry failed providers using the existing temporary file; never re-download."""
        if task.id in self._jobs and not self._jobs[task.id].done():
            raise RuntimeError("Task is already running")
        if task.status is not TaskStatus.FAILED:
            raise ValueError("Only failed tasks can be retried")
        if not task.file_path:
            raise FileNotFoundError("Temporary file is unavailable")
        job = asyncio.create_task(self._retry_job(task))
        self._jobs[task.id] = job
        return True

    async def _retry_job(self, task: Task) -> None:
        try:
            await self._upload_existing_file(task)
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            self.repository.save(task)
            raise
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc) or exc.__class__.__name__
            self.repository.save(task)
            await self.event_bus.publish(Event(EventType.TASK_FAILED, task.id, {"error": task.error}))
        finally:
            self._jobs.pop(task.id, None)

    async def cancel(self, task_id: str) -> bool:
        job = self._jobs.get(task_id)
        if job is None or job.done():
            return False
        job.cancel()
        return True

    def get_job(self, task_id: str) -> asyncio.Task[None] | None:
        return self._jobs.get(task_id)
