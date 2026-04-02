FROM node:22-slim AS viewer-builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
RUN npm run build:viewer


FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY config/ ./config/
COPY --from=viewer-builder /app/frontend/js/viewer.bundle.js ./frontend/js/viewer.bundle.js

EXPOSE 8000
CMD ["python", "backend/app.py"]
