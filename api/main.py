"""FastAPI entry point for cLOADER."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, HttpUrl

from core.events.bus import Event, EventBus
from core.models.task import Task, TaskStatus
from core.uploader.manager import UploadManager

app = FastAPI(title="cLOADER API", version="0.1.0")
event_bus = EventBus()
tasks: dict[str, Task] = {}


class CreateTaskRequest(BaseModel):
    url: HttpUrl
    providers: list[str] = Field(default_factory=list)
    filename: str | None = None


class TaskResponse(BaseModel):
    id: str
    url: str
    status: str
    filename: str | None
    providers: list[str]
    progress: float
    speed: float
    error: str | None = None


def task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        url=task.source_url,
        status=task.status.value,
        filename=task.final_filename,
        providers=task.selected_providers,
        progress=task.download_progress,
        speed=task.download_speed,
        error=task.error,
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "cloader"}


@app.get("/api/providers")
async def providers() -> dict[str, list[dict[str, str]]]:
    return {
        "providers": [
            {"id": "gofile", "name": "GoFile", "kind": "file"},
            {"id": "pixeldrain", "name": "Pixeldrain", "kind": "file"},
        ]
    }


@app.post("/api/tasks", response_model=TaskResponse, status_code=201)
async def create_task(request: CreateTaskRequest) -> TaskResponse:
    if not request.providers:
        raise HTTPException(status_code=400, detail="Select at least one provider")
    task = Task(
        id=uuid.uuid4().hex,
        source_url=str(request.url),
        selected_providers=list(dict.fromkeys(request.providers)),
        custom_filename=request.filename,
    )
    tasks[task.id] = task
    await event_bus.publish(Event.task_created(task.id, {"url": task.source_url}))
    return task_response(task)


@app.get("/api/tasks", response_model=list[TaskResponse])
async def list_tasks() -> list[TaskResponse]:
    return [task_response(task) for task in reversed(list(tasks.values()))]


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str) -> TaskResponse:
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_response(task)


@app.delete("/api/tasks/{task_id}")
async def cancel_task(task_id: str) -> dict[str, str]:
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.CANCELLED
    return {"status": "cancelled", "id": task_id}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = event_bus.create_queue()
    event_bus.add_queue(queue)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json({
                "type": event.type.value,
                "task_id": event.task_id,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
            })
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.remove_queue(queue)
