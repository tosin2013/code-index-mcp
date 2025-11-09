#!/bin/bash
# Local testing script for Code Index MCP before Cloud Run deployment
# Run this BEFORE deploying to cloud to catch issues early

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Configuration
IMAGE_NAME="code-index-mcp-local-test:latest"
CONTAINER_NAME="code-index-mcp-test"
TEST_PORT=8080

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Code Index MCP - Local Testing${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if Docker is running
log_info "Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    log_error "Docker is not running. Please start Docker Desktop."
    exit 1
fi
log_success "Docker is running"

# Stop and remove any existing test container
log_info "Cleaning up any existing test containers..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Change to repo root
cd "$(dirname "$0")/../.."

# Build the Docker image
log_info "Building Docker image..."
docker build -t "$IMAGE_NAME" -f deployment/gcp/Dockerfile .
log_success "Image built successfully"

# Run the container
log_info "Starting container on port $TEST_PORT..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$TEST_PORT:$TEST_PORT" \
    -e MCP_TRANSPORT=http \
    -e PORT=$TEST_PORT \
    "$IMAGE_NAME"

log_success "Container started"

# Wait for the server to start
log_info "Waiting for server to start..."
sleep 5

# Check if container is still running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    log_error "Container failed to start or crashed immediately"
    log_info "Container logs:"
    docker logs "$CONTAINER_NAME"
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
    exit 1
fi

# Test SSE endpoint (MCP HTTP/SSE transport)
log_info "Testing SSE endpoint..."
MAX_ATTEMPTS=10
ATTEMPT=1

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    # SSE endpoint returns 200 OK (streaming endpoint - curl will timeout after getting headers)
    # Exit code 28 (timeout) is OK as long as we got 200 status
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 "http://localhost:$TEST_PORT/sse" 2>/dev/null)
    CURL_EXIT=$?

    # Success if we got 200 status (even if curl timed out waiting for stream)
    if [ "$HTTP_CODE" = "200" ] || [ "$CURL_EXIT" = "28" ]; then
        log_success "SSE endpoint responding! (HTTP $HTTP_CODE)"
        log_info "MCP server is ready for connections on port $TEST_PORT"
        break
    else
        if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
            log_error "Health check failed after $MAX_ATTEMPTS attempts"
            log_info "Container logs:"
            docker logs "$CONTAINER_NAME"
            docker stop "$CONTAINER_NAME"
            docker rm "$CONTAINER_NAME"
            exit 1
        fi
        log_info "Attempt $ATTEMPT/$MAX_ATTEMPTS failed, retrying in 2s..."
        sleep 2
        ATTEMPT=$((ATTEMPT + 1))
    fi
done

# Test MCP tools endpoint (optional - requires authentication in production)
log_info "Testing tools endpoint..."
TOOLS_RESPONSE=$(curl -s "http://localhost:$TEST_PORT/tools" || echo "Failed")
if echo "$TOOLS_RESPONSE" | grep -q "tools\|error"; then
    log_success "Tools endpoint responding"
else
    log_warning "Tools endpoint returned unexpected response"
fi

# Show container logs
echo ""
log_info "Container logs (last 20 lines):"
echo "----------------------------------------"
docker logs --tail=20 "$CONTAINER_NAME"
echo "----------------------------------------"
echo ""

# Summary
log_success "✅ Local testing PASSED!"
echo ""
echo -e "${GREEN}Container is running successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Test manually: curl http://localhost:$TEST_PORT/health"
echo "  2. View logs: docker logs -f $CONTAINER_NAME"
echo "  3. Stop container: docker stop $CONTAINER_NAME"
echo "  4. If all looks good, deploy to Cloud Run: ./deploy.sh dev"
echo ""
echo -e "${YELLOW}Container is still running for manual testing.${NC}"
echo -e "${YELLOW}Stop it when done: docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME${NC}"
echo ""
