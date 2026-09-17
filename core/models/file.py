"""File metadata models."""

from dataclasses import dataclass


@dataclass(slots=True)
class FileInfo:
    """Metadata for a temporary local file."""

    path: str
    filename: str
    size: int = 0
    mime_type: str | None = None
    sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("File path cannot be empty")
        if not self.filename.strip():
            raise ValueError("Filename cannot be empty")
        if self.size < 0:
            raise ValueError("File size cannot be negative")
