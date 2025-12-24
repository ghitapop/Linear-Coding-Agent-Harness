# Autonomous Orchestrator Framework
# ==================================
# Multi-stage Docker build for the orchestrator

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create workspaces directory for projects
RUN mkdir -p /workspaces

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WORKSPACE_PATH=/workspaces \
    API_PORT=8080

# Expose API port (note: actual port is set via API_PORT env var)
EXPOSE ${API_PORT}

# Health check (uses API_PORT env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${API_PORT:-8080}/health || exit 1

# Default command - API server mode (reads API_PORT from environment)
CMD ["sh", "-c", "python main.py --api --host 0.0.0.0 --port ${API_PORT:-8080}"]
