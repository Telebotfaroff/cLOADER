FROM node:22-alpine AS frontend
WORKDIR /app/web
COPY web/package.json ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
COPY --from=frontend /app/web/dist ./web/dist
RUN mkdir -p /var/data /app/downloads
ENV CLOADER_DATA_DIR=/var/data
EXPOSE 10000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
