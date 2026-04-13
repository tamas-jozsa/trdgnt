# Dashboard: FastAPI backend + React frontend
# Multi-stage build

# --- Stage 1: Build React frontend ---
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY dashboard/frontend/package*.json ./
RUN npm ci
COPY dashboard/frontend/ ./
RUN npm run build

# --- Stage 2: Python backend + static frontend ---
FROM python:3.13-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies
COPY dashboard/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install main package (needed for imports)
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Copy backend code
COPY dashboard/backend/ ./backend/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./backend/static/

# Create runtime directories
RUN mkdir -p /app/data /app/trading_loop_logs /app/results

ENV PYTHONUNBUFFERED=1
ENV REDIS_URL=redis://redis:6379/0

EXPOSE 8888

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8888"]
