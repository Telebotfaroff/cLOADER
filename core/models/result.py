"""Upload result models."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class UploadStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass(slots=True)
class UploadResult:
    """Status and result of one provider upload."""

    task_id: str
    provider_id: str
    status: UploadStatus = UploadStatus.PENDING
    progress: float = 0.0
    uploaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    url: str | None = None
    error: str | None = None
    upload_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("Task id cannot be empty")
        self.provider_id = self.provider_id.strip().lower()
        if not self.provider_id:
            raise ValueError("Provider id cannot be empty")
        if not 0 <= self.progress <= 100:
            raise ValueError("Progress must be between 0 and 100")
        if self.uploaded_bytes < 0 or self.total_bytes < 0:
            raise ValueError("Byte counts cannot be negative")
        if self.speed < 0:
            raise ValueError("Speed cannot be negative")
