#!/bin/bash
# Quick Start Script for Ansible Deployment
# This script helps set up and run the first deployment

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "======================================"
echo "Code Index MCP - Ansible Quick Start"
echo "======================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check Ansible
if ! command -v ansible &> /dev/null; then
    echo "❌ Ansible not found. Installing..."
    pip install ansible
else
    echo "✅ Ansible found: $(ansible --version | head -1)"
fi

# Check gcloud
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
else
    echo "✅ gcloud found: $(gcloud version | head -1)"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker not found (optional for local builds)"
else
    echo "✅ Docker found: $(docker --version)"
fi

# Install Ansible collections
echo ""
echo "Installing Ansible collections..."
ansible-galaxy collection install -r requirements.yml

# Check GCP authentication
echo ""
echo "Checking GCP authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "❌ Not authenticated to GCP"
    echo "   Run: gcloud auth login"
    echo "   Then: gcloud auth application-default login"
    exit 1
fi

GCP_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
echo "✅ Authenticated as: $GCP_ACCOUNT"

# Get current project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ -z "$CURRENT_PROJECT" ]; then
    echo "❌ No GCP project set"
    echo "   Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi
echo "✅ GCP Project: $CURRENT_PROJECT"

# Select environment
echo ""
echo "Select deployment environment:"
echo "  1) dev (smaller resources, debug mode)"
echo "  2) prod (production resources, optimized)"
read -p "Enter choice [1]: " ENV_CHOICE
ENV_CHOICE=${ENV_CHOICE:-1}

if [ "$ENV_CHOICE" == "1" ]; then
    INVENTORY="inventory/dev.yml"
    ENV_NAME="dev"
else
    INVENTORY="inventory/prod.yml"
    ENV_NAME="prod"
fi

echo "✅ Environment: $ENV_NAME"

# Check if AlloyDB is provisioned
echo ""
echo "Checking AlloyDB status..."
if gcloud alloydb clusters list --region=us-east1 --project=$CURRENT_PROJECT --filter="name:code-index-cluster" --format="value(name)" &> /dev/null; then
    CLUSTER=$(gcloud alloydb clusters list --region=us-east1 --project=$CURRENT_PROJECT --filter="name:code-index-cluster" --format="value(name)" 2>/dev/null | head -1)
    if [ -n "$CLUSTER" ]; then
        echo "✅ AlloyDB cluster found: $CLUSTER"
        WITH_ALLOYDB="true"
    else
        echo "⚠️  No AlloyDB cluster found"
        echo "   Run Terraform first: cd .. && terraform init && terraform apply"
        read -p "Continue without AlloyDB? (y/n) [n]: " CONTINUE
        CONTINUE=${CONTINUE:-n}
        if [ "$CONTINUE" != "y" ]; then
            exit 1
        fi
        WITH_ALLOYDB="false"
    fi
else
    echo "⚠️  Could not check AlloyDB status"
    WITH_ALLOYDB="false"
fi

# Confirm deployment
echo ""
echo "======================================"
echo "Deployment Configuration"
echo "======================================"
echo "Project: $CURRENT_PROJECT"
echo "Environment: $ENV_NAME"
echo "Inventory: $INVENTORY"
echo "AlloyDB: $WITH_ALLOYDB"
echo "======================================"
echo ""
read -p "Proceed with deployment? (yes/no) [no]: " CONFIRM
CONFIRM=${CONFIRM:-no}

if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled"
    exit 0
fi

# Run deployment
echo ""
echo "Starting deployment..."
echo ""

ansible-playbook deploy.yml -i "$INVENTORY"

echo ""
echo "======================================"
echo "✅ Deployment Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Check deployment-summary-*.md for details"
echo "2. Configure Claude Desktop with provided config"
echo "3. Test semantic search tools"
echo ""
