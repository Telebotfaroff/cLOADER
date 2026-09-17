# cLOADER — Development Guide

## Project Goal

cLOADER is a Python-based download and upload manager with a separate Web UI.

The project MUST be divided into two major parts:

1. **Core** — Python engine responsible for downloading, task management, file handling, provider uploads, retries, persistence, and all business logic.
2. **Web UI** — Frontend and API layer responsible for displaying tasks, collecting user input, and communicating with the Core.

The Web UI must NOT contain provider-specific upload logic.

---

# 1. Architecture

Recommended architecture:

```text
Browser
   │
   │ HTTP + WebSocket
   ▼
┌──────────────────────────────┐
│           WEB UI             │
│                              │
│ React + TypeScript + Vite    │
│ Dashboard / Queue / History  │
└──────────────┬───────────────┘
               │
               │ REST API + WebSocket
               ▼
┌──────────────────────────────┐
│         CORE / API           │
│                              │
│ FastAPI                      │
│ Task Manager                 │
│ Download Manager             │
│ Upload Manager               │
│ Provider System              │
│ SQLite                       │
└──────────────┬───────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
   Downloader        Providers
                        │
              ┌─────────┼──────────┐
              ▼         ▼          ▼
            GoFile  Pixeldrain  Video Hosts
```

The Core must be usable independently of the Web UI.

For example, a future CLI or another application should be able to import the Core package directly.

---

# 2. Repository Structure

Use this structure:

```text
cLOADER/
│
├── core/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── task.py
│   │   ├── file.py
│   │   ├── provider.py
│   │   └── result.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── repositories.py
│   ├── downloader/
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   ├── http.py
│   │   └── media.py
│   ├── uploader/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── file/
│   │   │   ├── __init__.py
│   │   │   ├── gofile.py
│   │   │   └── pixeldrain.py
│   │   └── video/
│   │       ├── __init__.py
│   │       ├── streamtape.py
│   │       ├── vidshare.py
│   │       └── ...
│   ├── queue/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── events/
│   │   ├── __init__.py
│   │   └── bus.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── hashing.py
│   │   ├── filenames.py
│   │   ├── mime.py
│   │   └── filesystem.py
│   └── exceptions.py
│
├── api/
│   ├── __init__.py
│   ├── main.py
│   ├── routes/
│   │   ├── tasks.py
│   │   ├── providers.py
│   │   ├── settings.py
│   │   └── history.py
│   └── websocket.py
│
├── web/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       ├── services/
│       ├── types/
│       └── App.tsx
│
├── data/
│   └── .gitkeep
├── downloads/
│   └── .gitkeep
├── tests/
│   ├── core/
│   ├── providers/
│   └── api/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── guide.md
```

Do not create unnecessary duplicate files.

---

# PART 1 — CORE FUNCTIONS

## 3. Core Responsibility

The Core is the actual cLOADER engine.

It must handle:

- URL input
- Downloading
- Download progress
- Download speed
- ETA calculation
- Resume support where possible
- File naming
- Temporary files
- File validation
- SHA-256 hashing
- Queue management
- Concurrent tasks
- Upload management
- Provider selection
- Provider authentication
- Provider-specific upload implementations
- Upload progress
- Upload speed
- Retry handling
- Provider failure isolation
- Persistent task history
- Cleanup
- Events/state updates

The Core must not depend on React or browser code.

---

# 4. Task Lifecycle

Every task should follow a predictable state machine:

```text
QUEUED
  │
  ▼
DOWNLOADING
  │
  ├── FAILED
  │
  ▼
DOWNLOADED
  │
  ▼
UPLOADING
  │
  ├── some providers failed
  │
  ├── some providers completed
  │
  ▼
COMPLETED
```

Possible states:

```text
queued
downloading
downloaded
uploading
completed
failed
cancelled
paused
```

Provider-level states:

```text
pending
uploading
completed
failed
cancelled
retrying
```

Do not use one global status to represent every provider.

---

# 5. Task Model

A task should contain information similar to:

```python
Task:
    id
    source_url
    original_filename
    custom_filename
    final_filename
    file_size
    downloaded_bytes
    download_speed
    download_progress
    download_eta
    status
    selected_providers
    created_at
    started_at
    completed_at
    error
```

Provider upload result:

```python
UploadResult:
    task_id
    provider
    status
    progress
    uploaded_bytes
    total_bytes
    speed
    url
    error
    started_at
    completed_at
```

Use typed models/dataclasses or Pydantic models consistently.

---

# 6. Downloader

The downloader must:

- Stream data instead of loading entire files into RAM.
- Support direct HTTP/HTTPS downloads.
- Detect filename from headers/URL when possible.
- Support custom filename.
- Display progress.
- Calculate speed.
- Calculate ETA.
- Support resume when the server supports HTTP range requests.
- Handle connection errors.
- Retry temporary failures.
- Respect configurable timeouts.
- Verify the final file.
- Clean up incomplete files when appropriate.

For media pages, use a dedicated media extraction layer rather than putting site-specific logic into the generic HTTP downloader.

Keep HTTP downloader and media extractor separate.

---

# 7. Download Speed

Speed should be calculated using a moving/rolling window rather than only total bytes divided by total time. This produces a more useful real-time speed.

Expose:

```text
bytes_per_second
human_speed
percentage
downloaded_bytes
total_bytes
eta_seconds
```

The Web UI can then display:

```text
12.4 MB/s
2.1 GB / 4.8 GB
43.7%
ETA 3m 21s
```

---

# 8. Queue Manager

The queue manager controls:

- Pending tasks
- Active tasks
- Completed tasks
- Failed tasks
- Cancelled tasks

Configuration:

```text
max_concurrent_downloads
max_concurrent_uploads
max_retries
retry_delay
```

Download and upload concurrency MUST be independent.

Example:

```text
Downloads: 3 concurrent
Uploads:   4 concurrent
```

A completed download should be able to enter the upload queue without unnecessarily blocking another download.

Use asyncio primitives such as semaphores/queues where appropriate.

---

# 9. Upload Manager

The Upload Manager receives a completed local file and a provider list.

Example:

```python
upload_manager.upload(
    file_path=file,
    providers=[
        "gofile",
        "pixeldrain",
        "streamtape",
    ],
)
```

Each provider should run independently.

If:

```text
GoFile       SUCCESS
Pixeldrain   SUCCESS
Streamtape   FAILED
```

the task should not become completely failed.

The system should support retrying a failed provider without downloading the original file again.

---

# 10. Provider Interface

Every provider MUST implement the same abstract interface.

Conceptually:

```python
class UploadProvider:
    name: str

    async def upload(self, file_path, metadata):
        ...

    async def validate(self):
        ...

    async def cancel(self, upload_id):
        ...

    def supports_resume(self):
        ...
```

The exact interface may evolve during implementation.

Provider-specific code belongs ONLY inside its provider module.

Do not put provider URLs/endpoints inside the Web UI.

---

# 11. Provider Categories

Separate providers into:

```text
providers/
├── file/
│   ├── gofile.py
│   └── pixeldrain.py
│
└── video/
    ├── streamtape.py
    ├── vidshare.py
    └── ...
```

Initial required file providers:

- GoFile
- Pixeldrain

Video providers should be added individually after verifying their current upload API and authentication requirements.

Never invent provider API endpoints.

If an API is undocumented or unavailable, mark the provider as unsupported/unimplemented instead of creating fake functionality.

---

# 12. Provider Health

The Core should expose provider status:

```text
online
offline
authentication_required
configuration_error
rate_limited
temporarily_unavailable
unknown
```

The API can expose this information to the Web UI.

Optional future feature:

```text
Provider health check
Last successful upload
Last error
Failure count
```

---

# 13. Retry System

Use retry handling centrally.

Retry:

- Connection reset
- Timeout
- Temporary server error
- Rate-limit response when appropriate
- Temporary provider failure

Do not blindly retry permanent errors such as invalid credentials, unsupported file type, file-size limit exceeded, or invalid API request.

Use exponential backoff with a configurable maximum.

Example:

```text
Attempt 1 → wait 2 sec
Attempt 2 → wait 4 sec
Attempt 3 → wait 8 sec
Attempt 4 → wait 16 sec
```

Provider adapters may classify provider-specific errors.

---

# 14. Filename System

Support:

```text
Original filename
Custom filename
Filename template
Automatic filename
```

Templates may eventually support:

```text
{title}
{quality}
{id}
{date}
{extension}
```

Never allow unsafe path traversal such as `../../something`.

Sanitize filenames before creating files.

---

# 15. SQLite Database

Use SQLite for persistent state.

Do NOT store large video/file data in SQLite. Store metadata only.

Suggested tables:

```text
tasks
uploads
providers
settings
events
```

Example relationship:

```text
tasks
  │
  ├── uploads → GoFile
  ├── uploads → Pixeldrain
  └── uploads → Streamtape
```

This allows the system to restart without losing task history.

---

# 16. Crash Recovery

On startup, find tasks marked downloading/uploading and determine whether they can be resumed.

For downloads: resume if supported.

For uploads: resume if provider supports it; otherwise mark the provider upload for retry.

Do not automatically start dangerous duplicate uploads without checking stored state.

---

# 17. Events

The Core should publish events rather than directly manipulating the Web UI.

Examples:

```text
task.created
task.started
download.progress
download.completed
upload.started
upload.progress
upload.completed
upload.failed
task.completed
task.failed
task.cancelled
```

Example event:

```json
{
  "event": "download.progress",
  "task_id": "abc123",
  "progress": 63.4,
  "speed": 12400000,
  "downloaded_bytes": 2400000000,
  "total_bytes": 3800000000
}
```

This event system will feed the WebSocket layer.

---

# PART 2 — WEB UI

## 18. Web UI Responsibility

The Web UI is responsible only for:

- User input
- Task creation
- Task display
- Progress visualization
- Provider selection
- Filename input
- Queue controls
- History
- Settings
- Copying uploaded URLs
- Error display

The UI must not implement downloading or uploading itself.

---

# 19. Main Pages

Create these pages:

```text
Dashboard
Queue
Completed
Failed
History
Providers
Settings
```

A simple first version may combine Completed/Failed into History.

---

# 20. Dashboard

Show:

```text
Active downloads
Active uploads
Queued tasks
Completed today
Failed tasks
Total transferred
Current download speed
Current upload speed
```

---

# 21. Add Task UI

Required fields:

```text
URL
Custom filename (optional)
Provider selection
```

Example:

```text
Source URL
[________________________________________]

Filename
[________________________________________]

Upload to:

☑ GoFile
☑ Pixeldrain
☐ Streamtape
☐ Vidshare

[ Add to Queue ]
```

Support multiple URLs.

---

# 22. Queue UI

Each task should display:

```text
Filename
Status
Progress
Speed
ETA
Current stage
Provider statuses
Actions
```

Actions:

```text
Pause
Resume
Cancel
Retry
Delete
```

Only show actions that make sense for the current state.

---

# 23. Provider Progress

Display providers separately:

```text
GoFile
██████████████████░░ 91%
11.2 MB/s

Pixeldrain
████████████████████ 100%
✓ Completed

Streamtape
Waiting
```

Do not combine all provider progress into one misleading percentage.

---

# 24. Completed Task

Display filename, size, each provider result URL, Copy/Open controls, and a Copy All Links action.

Also include Retry Failed Uploads.

---

# 25. Real-Time Updates

Use REST API for commands/data retrieval.

Use WebSocket for real-time progress.

Do NOT repeatedly poll every task every second if WebSockets can provide the updates.

Example:

```text
Browser
   │
   ├── REST → create/cancel/retry
   │
   └── WebSocket ← progress/events
```

---

# 26. API Design

Recommended endpoints:

```text
GET    /api/tasks
POST   /api/tasks
GET    /api/tasks/{task_id}
POST   /api/tasks/{task_id}/pause
POST   /api/tasks/{task_id}/resume
POST   /api/tasks/{task_id}/cancel
POST   /api/tasks/{task_id}/retry
DELETE /api/tasks/{task_id}

GET    /api/providers
GET    /api/providers/{provider}
POST   /api/providers/{provider}/test

GET    /api/history
GET    /api/settings
PUT    /api/settings

WS     /ws/tasks
```

The API must call Core services. It should not contain actual provider implementation.

---

# 27. API Response Design

Use consistent JSON responses.

Example:

```json
{
  "id": "abc123",
  "filename": "movie.mp4",
  "status": "uploading",
  "download": {
    "progress": 100,
    "speed": 0,
    "downloaded_bytes": 1500000000,
    "total_bytes": 1500000000
  },
  "uploads": [
    {
      "provider": "gofile",
      "status": "uploading",
      "progress": 72,
      "speed": 8500000,
      "url": null
    }
  ]
}
```

Keep API models separate from internal implementation objects if that improves maintainability.

---

# 28. Web UI Design

Use a modern responsive dashboard.

Recommended:

```text
React
TypeScript
Vite
```

Prioritize clear progress, large readable status, fast interactions, mobile/desktop support, dark mode, copy-link buttons, toast notifications, and confirmation dialogs.

Do not overcomplicate the first version with unnecessary animations.

---

# 29. Settings

Settings should include:

```text
Download directory
Temporary directory
Maximum concurrent downloads
Maximum concurrent uploads
Maximum retries
Retry delay
Automatic cleanup
Default providers
Filename template
```

Provider credentials/settings should be managed separately.

Secrets must never be displayed in full after saving.

---

# 30. Security

For a local installation:

- Bind to localhost by default.
- Do not expose the API publicly by default.
- Validate all API inputs.
- Sanitize filenames.
- Avoid shell command injection.
- Do not commit API keys.
- Use `.env` for secrets where appropriate.
- Add `.env` to `.gitignore`.
- Limit filesystem access to configured directories where practical.

If remote access is added later, add authentication before exposing the service publicly.

---

# 31. Error Handling

Errors should be understandable.

Bad:

```text
HTTPError: 403...
```

Better:

```text
GoFile upload failed

Reason:
Authentication failed.

Action:
Check the GoFile configuration.
```

Keep technical details in logs while showing a concise message in the UI.

---

# 32. Logging

Create structured logs.

Example:

```text
2026-09-17 07:30:12 INFO  Task abc123 created
2026-09-17 07:30:13 INFO  Download started
2026-09-17 07:32:44 INFO  Download completed
2026-09-17 07:32:45 INFO  GoFile upload started
2026-09-17 07:35:02 INFO  GoFile upload completed
```

Do not log API secrets or passwords.

---

# 33. Testing

Tests must be added as features are implemented.

Core tests:

```text
Filename sanitization
Task state transitions
Queue behavior
Retry behavior
Database persistence
Speed calculation
Provider interface
```

Provider tests should mock network requests rather than uploading real files during normal unit tests.

API tests should cover create/get/cancel/retry task operations and provider status.

---

# 34. Performance Rules

IMPORTANT:

- Never load multi-GB files entirely into RAM.
- Stream downloads.
- Stream uploads.
- Use bounded concurrency.
- Avoid excessive WebSocket events.
- Batch/debounce high-frequency progress updates if necessary.
- Do not write a database row for every tiny progress increment.
- Keep temporary files on disk.
- Clean completed temporary files according to configuration.

---

# 35. Provider Implementation Rules

Every new provider must be added in isolation.

Example:

```text
providers/video/example.py
```

Do not modify downloader, queue, or web code unless the provider genuinely requires a new Core capability.

The provider adapter should handle authentication, upload initialization, upload request, multipart/chunk handling if required, upload progress, provider-specific errors, final URL extraction, and resume/cancellation if supported.

Before implementing a provider, verify its current API/documentation.

Never assume an old API still works.

---

# 36. Development Order

IMPORTANT: Develop the project in small steps. Do NOT generate the entire application in one huge change.

## Step 1 — Project skeleton

Create core/api/web/tests, basic configuration, and `.gitignore`. Do not implement providers yet.

## Step 2 — Core models

Implement Task, UploadResult, Provider, TaskStatus, and UploadStatus. Add unit tests. STOP and request approval before continuing.

## Step 3 — SQLite

Implement tasks/uploads/settings repositories. Test persistence. STOP and request approval.

## Step 4 — Event system

Implement internal task/download/upload events. Test event delivery. STOP and request approval.

## Step 5 — Downloader

Implement direct HTTP downloading with streaming, progress, speed, ETA, resume where supported, and retry. Test with a safe test file. STOP and request approval.

## Step 6 — Upload manager

Implement generic upload orchestration using a mock provider. STOP and request approval.

## Step 7 — GoFile provider

Verify the current official upload API first. Implement the provider adapter. Test upload and returned URL. STOP and request approval.

## Step 8 — Pixeldrain provider

Verify the current official API first. Implement the provider adapter. Test upload and returned URL. STOP and request approval.

## Step 9 — Video providers

Add video hosts one at a time. For every provider: verify current API, implement adapter, add tests/mocks, test authentication, test upload, test returned URL, and test failure handling. STOP after each provider or logical batch.

## Step 10 — FastAPI

Connect the API to Core and implement tasks/providers/history/settings/WebSocket. The API must remain thin. STOP and request approval.

## Step 11 — Web UI foundation

Create Dashboard, Queue, History, and Settings. Connect REST API. STOP and request approval.

## Step 12 — Real-time WebSocket UI

Add download progress, upload progress, speed, ETA, provider state, completion events, and error events. STOP and request approval.

## Step 13 — Polish

Add responsive layout, dark mode, copy buttons, toasts, search, filtering, provider health, bulk URL input, and filename templates. STOP and request approval.

---

# 37. Important AI Coding Instructions

If another AI coding assistant is used to develop this project, follow these rules:

### Rule 1 — One step at a time

Implement ONLY the current step. Do not automatically implement future steps.

After completing a step:

1. Explain what changed.
2. List modified/created files.
3. Explain how to test it.
4. Ask for approval to continue.

Use:

```text
STEP COMPLETE

Changes:
...

Files:
...

Test:
...

Waiting for approval for the next step.
```

### Rule 2 — Do not create huge files

Keep modules focused. Avoid files containing thousands of lines.

### Rule 3 — Do not duplicate logic

Centralize shared retry logic, progress calculation, task state handling, configuration, and provider orchestration.

### Rule 4 — Do not fake provider APIs

If provider documentation is unavailable, write `TODO: provider API verification required`. Do not invent endpoints, headers, authentication, or response formats.

### Rule 5 — Preserve working code

Before modifying an existing module, read it, understand dependencies, make the smallest appropriate change, and run relevant tests. Do not rewrite the entire project unnecessarily.

### Rule 6 — No secrets

Never commit API keys, passwords, tokens, cookies, or private credentials. Provide `.env.example` instead.

### Rule 7 — Test every major feature

Do not mark a feature complete merely because the code compiles. Run relevant tests.

### Rule 8 — Keep Core independent

This must remain possible:

```python
from core.downloader import ...
from core.uploader import ...
```

without importing React/browser code.

---

# 38. Future Features

Do not implement these initially unless specifically requested:

- User accounts
- Cloud database
- Remote multi-user access
- Mobile app
- Docker deployment
- Automatic provider discovery
- Complex analytics
- Distributed workers

Design the architecture so they can be added later.

---

# 39. Final Target

The finished cLOADER should work like:

```text
1. Open Web UI
        ↓
2. Paste URL
        ↓
3. Choose custom filename
        ↓
4. Select providers
        ↓
5. Add to queue
        ↓
6. Core downloads file
        ↓
7. UI shows progress, speed, and ETA
        ↓
8. Download completes
        ↓
9. Core uploads to selected providers
        ↓
10. UI shows each provider independently
        ↓
11. Upload URLs appear
        ↓
12. User can copy/open URLs
        ↓
13. History is saved in SQLite
```

The key architectural principle is:

```text
WEB UI = Presentation
API    = Communication
CORE   = Business Logic
PROVIDER = External Service Adapter
DATABASE = Persistent State
```

Keep these boundaries clean throughout development.
