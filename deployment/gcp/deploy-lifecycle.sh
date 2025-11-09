#!/bin/bash
#
# Code Index MCP - End-to-End Deployment Script
#
# This script automates the complete deployment lifecycle from DEPLOYMENT_LIFECYCLE.md
# It handles prerequisites checking, security setup, deployment, and verification.
#
# Usage:
#   ./deploy-lifecycle.sh [OPTIONS]
#
# Options:
#   --environment ENV    Deployment environment (dev/staging/prod) [default: dev]
#   --project-id ID      GCP project ID [required if not set in gcloud config]
#   --region REGION      GCP region [default: us-east1]
#   --user-email EMAIL   Email for API key generation [required]
#   --skip-hooks         Skip pre-commit hooks setup
#   --auto-approve       Skip confirmation prompts (use with caution)
#   --help               Show this help message
#
# Example:
#   ./deploy-lifecycle.sh --environment dev --user-email admin@example.com
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
REGION="us-east1"
PROJECT_ID=""
USER_EMAIL=""
SKIP_HOOKS=false
AUTO_APPROVE=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

confirm_action() {
    if [ "$AUTO_APPROVE" = true ]; then
        return 0
    fi

    echo ""
    echo -e "${YELLOW}$1${NC}"
    read -p "Continue? (yes/no): " -r
    echo
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_error "Deployment cancelled by user"
        exit 1
    fi
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 is not installed"
        return 1
    fi
    print_success "$1 is installed"
    return 0
}

show_help() {
    grep '^#' "$0" | grep -v '#!/bin/bash' | sed 's/^# //' | sed 's/^#//'
    exit 0
}

# ============================================================================
# Parse Command Line Arguments
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --project-id)
            PROJECT_ID="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --user-email)
            USER_EMAIL="$2"
            shift 2
            ;;
        --skip-hooks)
            SKIP_HOOKS=true
            shift
            ;;
        --auto-approve)
            AUTO_APPROVE=true
            shift
            ;;
        --help)
            show_help
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            ;;
    esac
done

# ============================================================================
# Prerequisites Check
# ============================================================================

print_header "Step 1: Checking Prerequisites"

print_info "Checking required tools..."
MISSING_TOOLS=false

check_command "gcloud" || MISSING_TOOLS=true
check_command "ansible" || MISSING_TOOLS=true
check_command "ansible-playbook" || MISSING_TOOLS=true
check_command "terraform" || MISSING_TOOLS=true
check_command "python3" || MISSING_TOOLS=true

if [ "$SKIP_HOOKS" = false ]; then
    check_command "pre-commit" || MISSING_TOOLS=true
    check_command "gitleaks" || MISSING_TOOLS=true
fi

if [ "$MISSING_TOOLS" = true ]; then
    print_error "Missing required tools. Please install them first:"
    echo ""
    echo "macOS:"
    echo "  brew install pre-commit gitleaks ansible terraform"
    echo "  brew install --cask google-cloud-sdk"
    echo ""
    echo "Linux:"
    echo "  # Install gcloud SDK: https://cloud.google.com/sdk/docs/install"
    echo "  pip install ansible"
    echo "  # Install terraform: https://www.terraform.io/downloads"
    echo "  pip install pre-commit"
    echo "  # Install gitleaks: https://github.com/gitleaks/gitleaks"
    exit 1
fi

print_success "All required tools are installed"

# ============================================================================
# GCP Configuration
# ============================================================================

print_header "Step 2: Verifying GCP Configuration"

# Check GCP authentication
print_info "Checking GCP authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    print_error "Not authenticated with GCP"
    echo ""
    echo "Please run:"
    echo "  gcloud auth login"
    echo "  gcloud auth application-default login"
    exit 1
fi

ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
print_success "Authenticated as: $ACTIVE_ACCOUNT"

# Get or verify project ID
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
    if [ -z "$PROJECT_ID" ]; then
        print_error "No GCP project configured"
        echo ""
        echo "Please run:"
        echo "  gcloud config set project YOUR_PROJECT_ID"
        echo ""
        echo "Or use: --project-id YOUR_PROJECT_ID"
        exit 1
    fi
fi

print_success "Using GCP project: $PROJECT_ID"

# Verify billing is enabled
print_info "Checking billing status..."
if ! gcloud beta billing projects describe "$PROJECT_ID" &> /dev/null; then
    print_warning "Could not verify billing status"
    print_info "Please ensure billing is enabled at:"
    print_info "https://console.cloud.google.com/billing"
    confirm_action "Billing is enabled for project $PROJECT_ID?"
else
    print_success "Billing is configured"
fi

# Get user email if not provided
if [ -z "$USER_EMAIL" ]; then
    print_warning "No user email provided for API key generation"
    read -p "Enter email for API key (e.g., admin@example.com): " USER_EMAIL
    if [ -z "$USER_EMAIL" ]; then
        print_error "User email is required"
        exit 1
    fi
fi

# ============================================================================
# Security Setup (Pre-commit Hooks)
# ============================================================================

if [ "$SKIP_HOOKS" = false ]; then
    print_header "Step 3: Setting Up Pre-commit Hooks"

    cd "$PROJECT_ROOT"

    if [ -d ".git" ]; then
        print_info "Installing pre-commit hooks..."

        # Install hooks
        if pre-commit install; then
            print_success "Pre-commit hooks installed"
        else
            print_error "Failed to install pre-commit hooks"
            exit 1
        fi

        # Test hooks
        print_info "Testing pre-commit hooks..."
        if pre-commit run --all-files; then
            print_success "Pre-commit hooks are working"
        else
            print_warning "Pre-commit hooks found issues (this is normal for first run)"
            print_info "Hooks are installed and will run on future commits"
        fi
    else
        print_warning "Not a git repository, skipping pre-commit hooks"
    fi
else
    print_info "Skipping pre-commit hooks setup (--skip-hooks)"
fi

# ============================================================================
# Deployment Configuration Review
# ============================================================================

print_header "Step 4: Reviewing Deployment Configuration"

echo "Deployment Details:"
echo "  Environment:  $ENVIRONMENT"
echo "  Project ID:   $PROJECT_ID"
echo "  Region:       $REGION"
echo "  User Email:   $USER_EMAIL"
echo ""
echo "Resources to be created:"
echo "  - AlloyDB cluster and instance (2 vCPU, 16 GB RAM)"
echo "  - Cloud Run service (auto-scaling)"
echo "  - VPC connector for private networking"
echo "  - GCS buckets for storage"
echo "  - Secret Manager secrets"
echo ""
echo "Estimated monthly cost: ~\$220 (see DEPLOYMENT_LIFECYCLE.md for breakdown)"
echo "Deployment time: ~30-40 minutes (AlloyDB provisioning is slowest)"
echo ""

confirm_action "Ready to deploy?"

# ============================================================================
# Ansible Deployment
# ============================================================================

print_header "Step 5: Deploying Infrastructure"

cd "$SCRIPT_DIR/ansible"

print_info "Starting Ansible deployment..."
print_info "This will take 30-40 minutes. Progress will be shown below."
echo ""

# Create log file
LOG_FILE="/tmp/code-index-mcp-deployment-$(date +%Y%m%d-%H%M%S).log"
print_info "Deployment log: $LOG_FILE"

# Run deployment
if ansible-playbook deploy.yml \
    -i "inventory/${ENVIRONMENT}.yml" \
    -e "confirm_deployment=yes" \
    2>&1 | tee "$LOG_FILE"; then
    print_success "Deployment completed successfully"
else
    print_error "Deployment failed. Check log: $LOG_FILE"
    exit 1
fi

# ============================================================================
# Deployment Verification
# ============================================================================

print_header "Step 6: Verifying Deployment"

# Get service URL
print_info "Getting Cloud Run service URL..."
SERVICE_NAME="code-index-mcp-${ENVIRONMENT}"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --format="value(status.url)" 2>/dev/null || echo "")

if [ -z "$SERVICE_URL" ]; then
    print_error "Could not get service URL"
    exit 1
fi
print_success "Service URL: $SERVICE_URL"

# Check service health
print_info "Checking service health..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/sse" || echo "000")

if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "401" ]; then
    print_success "Service is healthy (HTTP $HTTP_STATUS)"
else
    print_warning "Service returned HTTP $HTTP_STATUS"
    print_info "This might be normal if authentication is required"
fi

# Check AlloyDB
print_info "Checking AlloyDB status..."
CLUSTER_NAME="code-index-cluster-${ENVIRONMENT}"
CLUSTER_STATE=$(gcloud alloydb clusters describe "$CLUSTER_NAME" \
    --region="$REGION" \
    --format="value(state)" 2>/dev/null || echo "NOT_FOUND")

if [ "$CLUSTER_STATE" = "READY" ]; then
    print_success "AlloyDB cluster is READY"
else
    print_warning "AlloyDB cluster state: $CLUSTER_STATE"
fi

INSTANCE_NAME="code-index-primary-${ENVIRONMENT}"
INSTANCE_STATE=$(gcloud alloydb instances describe "$INSTANCE_NAME" \
    --cluster="$CLUSTER_NAME" \
    --region="$REGION" \
    --format="value(state)" 2>/dev/null || echo "NOT_FOUND")

if [ "$INSTANCE_STATE" = "READY" ]; then
    print_success "AlloyDB instance is READY"
else
    print_warning "AlloyDB instance state: $INSTANCE_STATE"
fi

# Check storage buckets
print_info "Checking storage buckets..."
PROJECTS_BUCKET="code-index-projects-${PROJECT_ID}"
GIT_BUCKET="code-index-git-repos-${PROJECT_ID}"

if gsutil ls "gs://${PROJECTS_BUCKET}/" &> /dev/null; then
    print_success "Projects bucket exists: $PROJECTS_BUCKET"
else
    print_warning "Projects bucket not found: $PROJECTS_BUCKET"
fi

if gsutil ls "gs://${GIT_BUCKET}/" &> /dev/null; then
    print_success "Git repos bucket exists: $GIT_BUCKET"
else
    print_warning "Git repos bucket not found: $GIT_BUCKET"
fi

# ============================================================================
# API Key Generation
# ============================================================================

print_header "Step 7: Generating API Key"

print_info "Generating API key for $USER_EMAIL..."

API_KEY_OUTPUT=$(ansible-playbook utilities.yml \
    -i "inventory/${ENVIRONMENT}.yml" \
    -e "operation=generate_api_key" \
    -e "user_email=${USER_EMAIL}" \
    2>&1)

API_KEY=$(echo "$API_KEY_OUTPUT" | grep -oE 'ci_[A-Za-z0-9]{64}' | head -1)

if [ -z "$API_KEY" ]; then
    print_error "Failed to generate API key"
    echo "$API_KEY_OUTPUT"
    exit 1
fi

print_success "API key generated successfully"

# ============================================================================
# Configuration Output
# ============================================================================

print_header "Deployment Complete! 🎉"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DEPLOYMENT SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Service Details:"
echo "  URL:         $SERVICE_URL"
echo "  Environment: $ENVIRONMENT"
echo "  Region:      $REGION"
echo "  Project:     $PROJECT_ID"
echo ""
echo "API Key (save this securely):"
echo "  $API_KEY"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_header "Claude Desktop Configuration"

CLAUDE_CONFIG_PATH="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

echo "Add this to: $CLAUDE_CONFIG_PATH"
echo ""
cat <<EOF
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "${SERVICE_URL}/sse",
      "transport": "sse",
      "headers": {
        "X-API-Key": "${API_KEY}"
      }
    }
  }
}
EOF
echo ""

print_header "Testing Your Deployment"

echo "1. Test service health:"
echo "   curl -H \"X-API-Key: ${API_KEY}\" ${SERVICE_URL}/sse"
echo ""
echo "2. Configure Claude Desktop (see above)"
echo ""
echo "3. In Claude Desktop, test ingestion:"
echo "   ingest_code_from_git(git_url=\"https://github.com/your/repo\")"
echo ""
echo "4. Test semantic search:"
echo "   semantic_search_code(query=\"authentication logic\", language=\"python\")"
echo ""

print_header "Important Security Notes"

echo "⚠️  Your API key is stored in Google Secret Manager"
echo "⚠️  Pre-commit hooks will prevent accidental key commits"
echo "⚠️  To revoke this key, run:"
echo "    gcloud secrets delete code-index-api-key-${USER_EMAIL}-${ENVIRONMENT}"
echo ""

print_header "Cost Management"

echo "Monthly estimated cost: ~\$220 (see DEPLOYMENT_LIFECYCLE.md)"
echo ""
echo "To reduce costs:"
echo "  - Service auto-scales to zero when idle"
echo "  - Automatic cleanup runs daily (90-day retention)"
echo "  - For complete teardown, run:"
echo "    cd $SCRIPT_DIR/ansible"
echo "    ansible-playbook utilities.yml -i inventory/${ENVIRONMENT}.yml \\"
echo "      -e '{\"operation\": \"teardown\", \"auto_approve\": true, \"delete_buckets\": true}'"
echo ""

print_header "Next Steps"

echo "1. Configure Claude Desktop with the configuration above"
echo "2. Restart Claude Desktop"
echo "3. Test ingestion with a small repository"
echo "4. Try semantic search on your codebase"
echo "5. Set up monitoring and alerts in GCP Console"
echo "6. Review cost optimization options"
echo ""
echo "For detailed documentation, see:"
echo "  - DEPLOYMENT_LIFECYCLE.md - Complete lifecycle guide"
echo "  - docs/adrs/ - Architecture decision records"
echo "  - tests/ansible/README.md - Testing guide"
echo ""

print_success "Deployment lifecycle complete!"
print_info "Deployment log saved to: $LOG_FILE"

exit 0
