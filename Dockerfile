# Base image for all trdagnt trading services
# Used by: discovery, portfolio-review, news-monitor
FROM python:3.13-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cache layer)
COPY pyproject.toml ./
COPY requirements.txt ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY apps/ ./apps/
COPY cli/ ./cli/
COPY config/ ./config/
COPY docs/ ./docs/
COPY scripts/ ./scripts/

# Create runtime directories
RUN mkdir -p /app/data/theses \
             /app/data/discovery \
             /app/data/reviews \
             /app/data/news_events \
             /app/trading_loop_logs/memory \
             /app/trading_loop_logs/reports \
             /app/results

# Install the package
COPY pyproject.toml setup.cfg* ./
RUN pip install --no-cache-dir -e .

# Default environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONWARNINGS=ignore
ENV REDIS_URL=redis://redis:6379/0

# --- Discovery Pipeline ---
FROM base AS discovery
CMD ["python", "apps/discovery_pipeline.py"]

# --- Portfolio Review ---
FROM base AS portfolio-review
CMD ["python", "apps/portfolio_review.py"]

# --- News Monitor ---
FROM base AS news-monitor
CMD ["python", "apps/news_monitor.py"]
