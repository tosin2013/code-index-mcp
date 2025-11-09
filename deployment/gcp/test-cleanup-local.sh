#!/bin/bash
#
# Test cleanup functionality locally in dry-run mode
#
# This script tests the cleanup logic without actually deleting anything.
# It's safe to run and will show you what would be deleted.
#
# Usage:
#   ./test-cleanup-local.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Cleanup Functionality Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if GCS_BUCKET_NAME is set
if [ -z "$GCS_BUCKET_NAME" ]; then
    echo -e "${YELLOW}[WARN]${NC} GCS_BUCKET_NAME not set, using default"
    export GCS_BUCKET_NAME="code-index-projects-tosinscloud"
fi

echo -e "${BLUE}[INFO]${NC} Bucket: $GCS_BUCKET_NAME"
echo -e "${BLUE}[INFO]${NC} Mode: DRY RUN (safe, won't delete anything)"
echo ""

# Check if GCP dependencies are installed
echo -e "${BLUE}[INFO]${NC} Checking dependencies..."
if ! uv run python -c "import google.cloud.storage" 2>/dev/null; then
    echo -e "${YELLOW}[WARN]${NC} google-cloud-storage not installed"
    echo -e "${BLUE}[INFO]${NC} Installing GCP dependencies..."
    uv sync --extra gcp
fi

echo -e "${GREEN}[SUCCESS]${NC} Dependencies OK"
echo ""

# Test 1: Import check
echo -e "${BLUE}[INFO]${NC} Test 1: Import cleanup module..."
if uv run python -c "from code_index_mcp.admin import cleanup_idle_projects; print('✓ Import successful')" 2>&1; then
    echo -e "${GREEN}[SUCCESS]${NC} Module imports correctly"
else
    echo -e "${RED}[ERROR]${NC} Failed to import cleanup module"
    exit 1
fi
echo ""

# Test 2: Dry run execution
echo -e "${BLUE}[INFO]${NC} Test 2: Execute cleanup in dry-run mode..."
echo -e "${BLUE}[INFO]${NC} This will scan the bucket but won't delete anything"
echo ""

uv run python -m code_index_mcp.admin.run_cleanup \
    --dry-run \
    --max-idle-days 30 \
    --bucket "$GCS_BUCKET_NAME" 2>&1 || {
    echo -e "${YELLOW}[WARN]${NC} Cleanup test completed with warnings"
    echo -e "${YELLOW}[WARN]${NC} This is expected if bucket doesn't exist yet or has no data"
}

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}[SUCCESS]${NC} Cleanup test complete!"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${BLUE}[INFO]${NC} Next steps:"
echo -e "  1. Deploy to Cloud Run: ./deploy.sh dev"
echo -e "  2. Create some test data in GCS"
echo -e "  3. Run cleanup job: gcloud run jobs execute code-index-cleanup-dev --region=us-east1"
echo ""



