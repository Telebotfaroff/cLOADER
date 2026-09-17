"""Application wiring for the FastAPI process."""

from __future__ import annotations

import os
from pathlib import Path

from core.database.database import Database
from core.database.repositories import TaskRepository
from core.downloader.manager import DownloadManager
from core.events import EventBus
from core.providers.file.gofile import GofileProvider
from core.providers.file.pixeldrain import PixeldrainProvider
from core.uploader.manager import UploadManager
from core.service.task_service import TaskService


def build_service() -> tuple[Database, TaskRepository, EventBus, TaskService]:
    data_dir = Path(os.getenv("CLOADER_DATA_DIR", "data"))
    download_dir = Path(os.getenv("CLOADER_DOWNLOAD_DIR", str(data_dir / "downloads")))
    database = Database(data_dir / "cloader.db")
    repository = TaskRepository(database)
    event_bus = EventBus()

    # GoFile uses guest uploads by default. No account or API token is required.
    # A token is intentionally not read from the environment here.
    providers = {
        "gofile": GofileProvider(),
        "pixeldrain": PixeldrainProvider(api_key=os.getenv("PIXELDRAIN_API_KEY")),
    }
    uploader = UploadManager(
        providers,
        event_bus=event_bus,
        max_concurrency=max(1, int(os.getenv("CLOADER_UPLOAD_CONCURRENCY", "2"))),
        max_retries=max(0, int(os.getenv("CLOADER_UPLOAD_RETRIES", "2"))),
    )
    downloader = DownloadManager(download_dir=download_dir)
    service = TaskService(repository, downloader, uploader, event_bus)
    return database, repository, event_bus, service
