# Use lightweight Python image
FROM python:3.11-slim

# Install git (for code analysis) with --no-install-recommends to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Create non-root user for security (UID 1000 matches Cloud Run security context)
RUN groupadd -r mcpuser --gid=1000 && useradd -r -g mcpuser --uid=1000 mcpuser

# Set working directory
WORKDIR /app

# Copy dependency list and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Change ownership to non-root user
RUN chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Set Python path
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/src"

# Health check - verify Python interpreter is responsive
# For stdio-based MCP servers, we check if Python can execute basic commands
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import sys; sys.exit(0)" || exit 1

# No default project directory mount point needed, user will explicitly set project path

# Run MCP tool
# MCP server uses stdio mode by default
ENTRYPOINT ["python", "-m", "code_index_mcp.server"]
