FROM node:22-slim AS viewer-builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
RUN npm run build:viewer

COPY portal_ui/package.json portal_ui/package-lock.json ./portal_ui/
RUN npm --prefix portal_ui ci

COPY portal_ui/ ./portal_ui/
RUN npm --prefix portal_ui run build


FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY --from=viewer-builder /app/frontend/js/viewer.bundle.js ./frontend/js/viewer.bundle.js
COPY --from=viewer-builder /app/frontend/portal ./frontend/portal

EXPOSE 8000
CMD ["python", "backend/app.py"]
