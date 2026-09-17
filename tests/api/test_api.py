"""Basic API contract tests."""

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_providers() -> None:
    response = client.get("/api/providers")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["providers"]}
    assert {"gofile", "pixeldrain"} <= ids


def test_create_and_get_task() -> None:
    response = client.post("/api/tasks", json={
        "url": "https://example.com/video.mp4",
        "providers": ["gofile", "pixeldrain"],
        "filename": "demo.mp4",
    })
    assert response.status_code == 201
    task_id = response.json()["id"]

    fetched = client.get(f"/api/tasks/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["filename"] == "demo.mp4"


def test_create_requires_provider() -> None:
    response = client.post("/api/tasks", json={
        "url": "https://example.com/video.mp4",
        "providers": [],
    })
    assert response.status_code == 400
