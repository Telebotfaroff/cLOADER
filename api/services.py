"""Application wiring for the FastAPI process."""

from core.database.database import Database
from core.database.repositories import TaskRepository
from core.downloader.manager import DownloadManager
from core.events import EventBus
from core.providers.file.gofile import GofileProvider
from core.providers.file.pixeldrain import PixeldrainProvider
from core.uploader.manager import UploadManager
from core.service.task_service import TaskService


def build_service() -> tuple[Database, TaskRepository, EventBus, TaskService]:
    database = Database()
    repository = TaskRepository(database)
    event_bus = EventBus()
    providers = {
        "gofile": GofileProvider(),
        "pixeldrain": PixeldrainProvider(),
    }
    uploader = UploadManager(providers, event_bus=event_bus, max_concurrency=2, max_retries=2)
    downloader = DownloadManager()
    service = TaskService(repository, downloader, uploader, event_bus)
    return database, repository, event_bus, service
