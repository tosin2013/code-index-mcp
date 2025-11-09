# Dockerfile for Code Index MCP Server - Google Cloud Run
# Multi-stage build for optimal image size and security
# 
# Build: docker build -t code-index-mcp -f deployment/gcp/Dockerfile .
# Run:   docker run -p 8080:8080 -e MCP_TRANSPORT=http code-index-mcp
#
# Target image size: ~200MB (vs ~1GB with single-stage)
# Confidence: 90%

# Stage 1: Builder
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml README.md ./
COPY src ./src

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Install dependencies (including GCP extras)
RUN uv pip install --system --no-cache ".[gcp]"

# Stage 2: Runtime
FROM python:3.11-slim

# Install runtime dependencies including git for Git-sync (Phase 3A)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash mcp && \
    mkdir -p /app /home/mcp/.code_indexer && \
    chown -R mcp:mcp /app /home/mcp

# Set working directory
WORKDIR /app

# Copy Python environment from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=mcp:mcp src ./src
COPY --chown=mcp:mcp pyproject.toml README.md ./

# Switch to non-root user
USER mcp

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_TRANSPORT=http \
    PORT=8080

# Expose port
EXPOSE 8080

# Health check - SSE endpoint for MCP
# Cloud Run will check if the server is responding on port 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/sse').read()" || exit 1

# Run the server
CMD ["python", "-m", "code_index_mcp.server"]

