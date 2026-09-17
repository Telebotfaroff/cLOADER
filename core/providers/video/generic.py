"""Generic video-host adapter base for HTTP upload endpoints."""

from __future__ import annotations

from core.providers.base import UploadProvider


class GenericVideoProvider(UploadProvider):
    """Placeholder base for video hosts with provider-specific protocols.

    Concrete hosts should subclass UploadProvider and implement their documented
    API rather than pretending that all video hosts share one endpoint.
    """

    def __init__(self, provider_id: str, name: str) -> None:
        self.id = provider_id
        self.name = name

    async def upload(self, *args, **kwargs):
        raise NotImplementedError(
            f"{self.name} requires a provider-specific API adapter."
        )
