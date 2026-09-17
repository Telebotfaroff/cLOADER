"""Small in-process event bus used to publish task progress updates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable


class EventType(str, Enum):
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    DOWNLOAD_STARTED = "download.started"
    DOWNLOAD_PROGRESS = "download.progress"
    DOWNLOAD_COMPLETED = "download.completed"
    DOWNLOAD_FAILED = "download.failed"
    UPLOAD_STARTED = "upload.started"
    UPLOAD_PROGRESS = "upload.progress"
    UPLOAD_COMPLETED = "upload.completed"
    UPLOAD_FAILED = "upload.failed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


@dataclass(frozen=True, slots=True)
class Event:
    """Immutable event delivered to subscribers."""

    type: EventType
    task_id: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    """In-process pub/sub bus with async-safe dispatch."""

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        async with self._lock:
            handlers = self._subscribers.setdefault(event_type, [])
            if handler not in handlers:
                handlers.append(handler)

    async def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        async with self._lock:
            handlers = self._subscribers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)
            if not handlers:
                self._subscribers.pop(event_type, None)

    async def publish(self, event: Event) -> None:
        """Dispatch an event to all current subscribers.

        Handlers are isolated: one handler raising an exception does not prevent
        the remaining handlers from receiving the event.
        """
        async with self._lock:
            handlers = tuple(self._subscribers.get(event.type, ()))

        if not handlers:
            return

        results = await asyncio.gather(
            *(self._invoke(handler, event) for handler in handlers),
            return_exceptions=True,
        )
        # Exceptions are intentionally consumed here. Logging can be added at
        # the API/application boundary without coupling the core bus to logging.
        _ = results

    @staticmethod
    async def _invoke(handler: EventHandler, event: Event) -> None:
        result = handler(event)
        if asyncio.iscoroutine(result):
            await result
