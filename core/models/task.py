"""Download/upload task model."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .result import UploadResult


class TaskStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass(slots=True)
class Task:
    """Represents one complete cLOADER job."""

    id: str
    source_url: str
    original_filename: str | None = None
    custom_filename: str | None = None
    final_filename: str | None = None
    status: TaskStatus = TaskStatus.QUEUED
    selected_providers: list[str] = field(default_factory=list)
    uploads: list[UploadResult] = field(default_factory=list)
    file_path: str | None = None
    file_size: int = 0
    downloaded_bytes: int = 0
    download_speed: float = 0.0
    download_progress: float = 0.0
    download_eta: float | None = None
    file_sha256: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        self.source_url = self.source_url.strip()
        if not self.id:
            raise ValueError("Task id cannot be empty")
        if not self.source_url:
            raise ValueError("Source URL cannot be empty")
        if self.file_size < 0 or self.downloaded_bytes < 0:
            raise ValueError("Byte counts cannot be negative")
        if not 0 <= self.download_progress <= 100:
            raise ValueError("Download progress must be between 0 and 100")
        if self.download_speed < 0:
            raise ValueError("Download speed cannot be negative")
        if self.download_eta is not None and self.download_eta < 0:
            raise ValueError("Download ETA cannot be negative")
        self.selected_providers = [p.strip().lower() for p in self.selected_providers if p.strip()]

    @property
    def provider_count(self) -> int:
        return len(self.selected_providers)

    @property
    def successful_uploads(self) -> list[UploadResult]:
        return [u for u in self.uploads if u.status.value == "completed"]

    @property
    def failed_uploads(self) -> list[UploadResult]:
        return [u for u in self.uploads if u.status.value == "failed"]
