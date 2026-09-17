"""Domain models used by cLOADER."""

from .file import FileInfo
from .provider import ProviderCapabilities, ProviderInfo, ProviderKind
from .result import UploadResult, UploadStatus
from .task import Task, TaskStatus

__all__ = [
    "FileInfo",
    "ProviderCapabilities",
    "ProviderInfo",
    "ProviderKind",
    "Task",
    "TaskStatus",
    "UploadResult",
    "UploadStatus",
]
