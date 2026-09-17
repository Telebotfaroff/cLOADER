"""Tests for the cLOADER event bus."""

import asyncio
import unittest

from core.events import Event, EventBus, EventType


class EventBusTests(unittest.TestCase):
    def test_async_subscriber_receives_event(self):
        async def scenario():
            bus = EventBus()
            received = []

            async def handler(event):
                received.append(event)

            await bus.subscribe(EventType.DOWNLOAD_PROGRESS, handler)
            event = Event(
                EventType.DOWNLOAD_PROGRESS,
                "task-1",
                {"progress": 42.5, "speed": 1024},
            )
            await bus.publish(event)

            self.assertEqual(received, [event])
            self.assertEqual(received[0].data["progress"], 42.5)

        asyncio.run(scenario())

    def test_sync_subscriber_and_unsubscribe(self):
        async def scenario():
            bus = EventBus()
            received = []

            def handler(event):
                received.append(event.task_id)

            await bus.subscribe(EventType.TASK_UPDATED, handler)
            await bus.publish(Event(EventType.TASK_UPDATED, "task-1"))
            await bus.unsubscribe(EventType.TASK_UPDATED, handler)
            await bus.publish(Event(EventType.TASK_UPDATED, "task-2"))

            self.assertEqual(received, ["task-1"])

        asyncio.run(scenario())

    def test_handler_failure_does_not_block_other_handlers(self):
        async def scenario():
            bus = EventBus()
            received = []

            async def broken_handler(event):
                raise RuntimeError("test failure")

            async def working_handler(event):
                received.append(event.task_id)

            await bus.subscribe(EventType.UPLOAD_PROGRESS, broken_handler)
            await bus.subscribe(EventType.UPLOAD_PROGRESS, working_handler)
            await bus.publish(Event(EventType.UPLOAD_PROGRESS, "task-1"))

            self.assertEqual(received, ["task-1"])

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
