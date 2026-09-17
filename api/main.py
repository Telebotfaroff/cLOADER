"""FastAPI entry point for cLOADER."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, HttpUrl

from core.events import Event, EventType
from core.models import Task
from api.services import build_service

app = FastAPI(title="cLOADER API", version="0.2.0")
database, repository, event_bus, task_service = build_service()


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
    uploads: list[dict[str, str | None]] = Field(default_factory=list)


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
        uploads=[
            {"provider": u.provider_id, "status": u.status.value, "url": u.url, "error": u.error}
            for u in task.uploads
        ],
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "cloader"}


@app.get("/api/providers")
async def providers() -> dict[str, list[dict[str, str]]]:
    return {"providers": [
        {"id": "gofile", "name": "GoFile", "kind": "file", "configured": "true"},
        {"id": "pixeldrain", "name": "Pixeldrain", "kind": "file", "configured": "true"},
    ]}


@app.post("/api/tasks", response_model=TaskResponse, status_code=201)
async def create_task(request: CreateTaskRequest) -> TaskResponse:
    providers = list(dict.fromkeys(p.lower() for p in request.providers))
    if not providers:
        raise HTTPException(status_code=400, detail="Select at least one provider")
    unknown = [p for p in providers if p not in {"gofile", "pixeldrain"}]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown providers: {', '.join(unknown)}")
    task = Task(
        id=uuid.uuid4().hex,
        source_url=str(request.url),
        selected_providers=providers,
        custom_filename=request.filename,
    )
    await task_service.create_and_start(task)
    return task_response(task)


@app.get("/api/tasks", response_model=list[TaskResponse])
async def list_tasks() -> list[TaskResponse]:
    return [task_response(task) for task in repository.list()]


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str) -> TaskResponse:
    task = repository.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_response(task)


@app.delete("/api/tasks/{task_id}")
async def cancel_task(task_id: str) -> dict[str, str]:
    task = repository.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    cancelled = await task_service.cancel(task_id)
    if not cancelled:
        task.error = task.error or "Task is not currently running"
        repository.save(task)
    return {"status": "cancelled" if cancelled else task.status.value, "id": task_id}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=500)

    async def forward(event: Event) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await queue.put(event)

    for event_type in EventType:
        await event_bus.subscribe(event_type, forward)
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
        for event_type in EventType:
            await event_bus.unsubscribe(event_type, forward)
