"""Provider models and capabilities."""

from dataclasses import dataclass, field
from enum import Enum


class ProviderKind(str, Enum):
    FILE = "file"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Features supported by an upload provider."""

    progress: bool = True
    resume: bool = False
    cancellation: bool = True


@dataclass(slots=True)
class ProviderInfo:
    """Runtime metadata for a configured provider."""

    id: str
    name: str
    kind: ProviderKind
    enabled: bool = True
    configured: bool = False
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)

    def __post_init__(self) -> None:
        self.id = self.id.strip().lower()
        if not self.id:
            raise ValueError("Provider id cannot be empty")
        if not self.name.strip():
            raise ValueError("Provider name cannot be empty")
