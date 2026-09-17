# cLOADER

cLOADER is a personal transfer manager that downloads a source URL to temporary storage, uploads the file to selected providers, reports live progress, and removes the temporary file after all selected uploads succeed.

## Features

- FastAPI backend with WebSocket live events
- React + Vite web interface
- HTTP/HTTPS streaming downloads
- GoFile and Pixeldrain adapters
- Concurrent provider uploads with retries
- Retry failed providers without downloading the source again
- SQLite task history
- Automatic temporary-file cleanup after complete success
- Single-service Render deployment
- Docker production image

## Local development

### Backend

```bash
python -m pip install -r requirements.txt
uvicorn api.main:app --reload
```

### Frontend development

```bash
cd web
npm install
npm run dev
```

For local frontend development, set `VITE_API_BASE` to the backend origin if Vite and FastAPI are running on different ports.

## Production

The repository includes `Dockerfile` and `render.yaml` for a single Render web service. The container builds the React application and runs FastAPI. FastAPI serves the generated React application, API routes, and `/ws` from the same origin.

The Render configuration mounts a persistent disk at `/var/data` and sets `CLOADER_DATA_DIR=/var/data`, so SQLite and temporary downloads survive application restarts.

Optional environment variables:

- `GOFILE_TOKEN`
- `PIXELDRAIN_API_KEY`
- `CLOADER_UPLOAD_CONCURRENCY`
- `CLOADER_UPLOAD_RETRIES`
- `CLOADER_DATA_DIR`
- `CLOADER_DOWNLOAD_DIR`

## Tests

Backend tests run with:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Frontend CI installs the pinned package versions and runs `npm run build`.
