#!/bin/bash
# Setup Terraform remote backend (GCS bucket)
# Run this ONCE before first deployment

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-us-east1}"
BUCKET_NAME="code-index-terraform-state"

echo "======================================"
echo "Terraform Backend Setup"
echo "======================================"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Bucket: ${BUCKET_NAME}"
echo "======================================"
echo ""

# Check if bucket already exists
if gsutil ls -p "${PROJECT_ID}" "gs://${BUCKET_NAME}" &>/dev/null; then
    echo "✅ Bucket gs://${BUCKET_NAME} already exists"
else
    echo "Creating GCS bucket for Terraform state..."
    gsutil mb -p "${PROJECT_ID}" -l "${REGION}" "gs://${BUCKET_NAME}"
    echo "✅ Bucket created: gs://${BUCKET_NAME}"
fi

# Enable versioning for state file protection
echo "Enabling versioning on state bucket..."
gsutil versioning set on "gs://${BUCKET_NAME}"
echo "✅ Versioning enabled"

# Set lifecycle policy to keep only last 3 versions
echo "Setting lifecycle policy to retain last 3 versions..."
cat > /tmp/lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [{
      "action": {"type": "Delete"},
      "condition": {"numNewerVersions": 3}
    }]
  }
}
EOF

gsutil lifecycle set /tmp/lifecycle.json "gs://${BUCKET_NAME}"
rm /tmp/lifecycle.json
echo "✅ Lifecycle policy applied"

echo ""
echo "======================================"
echo "✅ Terraform backend setup complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Commit the changes to alloydb-dev.tf"
echo "2. Run delete-gcp.yml workflow to clean up existing resources"
echo "3. Re-run deployment workflow"
