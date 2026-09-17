"""Base interface for upload providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable


ProgressCallback = Callable[[int, int, float], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class ProviderUpload:
    """Normalized provider response."""

    url: str
    upload_id: str | None = None


class UploadProvider(ABC):
    """Interface every file/video host adapter must implement."""

    id: str
    name: str

    @abstractmethod
    async def upload(
        self,
        file_path: str | Path,
        filename: str,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> ProviderUpload:
        """Upload a local file and return its public result."""
        raise NotImplementedError
