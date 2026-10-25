# ---- build React ----
FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Python API + built UI ----
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=ui /ui/dist ./static
ENV PORT=8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
