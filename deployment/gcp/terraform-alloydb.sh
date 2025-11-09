#!/bin/bash
# Terraform wrapper script for AlloyDB operations
# Simplifies Terraform commands for use in Ansible and CI/CD

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

OPERATION=${1:-}
ENV=${2:-dev}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

usage() {
    cat << EOF
Usage: $0 <operation> [environment]

Operations:
  apply     - Create/update AlloyDB infrastructure
  destroy   - Delete AlloyDB infrastructure
  plan      - Show planned changes
  output    - Show Terraform outputs
  validate  - Validate Terraform configuration
  status    - Check AlloyDB cluster status

Arguments:
  environment - Environment name (default: dev)

Examples:
  $0 apply dev           # Deploy to dev environment
  $0 destroy dev         # Destroy dev environment
  $0 plan prod           # Plan production changes
  $0 status dev          # Check dev cluster status

Environment Variables:
  TF_AUTO_APPROVE - Set to 'false' to require manual approval (default: true)
  TF_TIMEOUT      - Terraform timeout in seconds (default: 1800)

EOF
    exit 1
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v terraform &> /dev/null; then
        log_error "terraform is not installed. Install from https://www.terraform.io/downloads"
        exit 1
    fi

    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud is not installed. Install from https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    # Check gcloud authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        log_error "Not authenticated with gcloud. Run: gcloud auth login"
        exit 1
    fi

    log "✅ Prerequisites check passed"
}

init_terraform() {
    log_info "Initializing Terraform..."
    cd "$SCRIPT_DIR"

    if [ ! -d ".terraform" ]; then
        terraform init
    else
        terraform init -upgrade
    fi
}

apply_infrastructure() {
    log "=========================================="
    log "  Applying AlloyDB Infrastructure"
    log "=========================================="
    log_info "Environment: $ENV"
    log_info "This will create:"
    log_info "  - AlloyDB cluster (code-index-cluster-$ENV)"
    log_info "  - AlloyDB instance (primary-instance-$ENV)"
    log_info "  - VPC network and peering"
    log_info "  - Allocated IP range"
    log_warning "Estimated time: 15-20 minutes"
    log_warning "Cost: ~$180-200/month when running"
    echo ""

    AUTO_APPROVE=${TF_AUTO_APPROVE:-true}

    if [ "$AUTO_APPROVE" != "true" ]; then
        read -p "Proceed with deployment? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            log_info "Deployment cancelled"
            exit 0
        fi
    fi

    cd "$SCRIPT_DIR"

    # Run terraform apply
    log_info "Running terraform apply..."
    if terraform apply -auto-approve; then
        log "✅ Infrastructure deployment successful"

        # Wait for cluster to be ready
        log_info "Waiting for AlloyDB cluster to be READY..."
        local max_wait=900  # 15 minutes
        local elapsed=0
        local interval=30

        while [ $elapsed -lt $max_wait ]; do
            local state=$(gcloud alloydb clusters describe "code-index-cluster-$ENV" \
                --region=us-east1 \
                --format='value(state)' 2>/dev/null || echo "NOT_FOUND")

            if [ "$state" = "READY" ]; then
                log "✅ AlloyDB cluster is READY"
                break
            elif [ "$state" = "NOT_FOUND" ]; then
                log_error "Cluster not found. Deployment may have failed."
                exit 1
            else
                log_info "Cluster state: $state (waiting...)"
                sleep $interval
                elapsed=$((elapsed + interval))
            fi
        done

        if [ $elapsed -ge $max_wait ]; then
            log_warning "Cluster did not become READY within $max_wait seconds"
            log_warning "Check status manually: gcloud alloydb clusters describe code-index-cluster-$ENV --region=us-east1"
        fi

        # Display outputs
        log_info "Terraform outputs:"
        terraform output
    else
        log_error "Infrastructure deployment failed"
        exit 1
    fi
}

destroy_infrastructure() {
    log "=========================================="
    log "  ⚠️  DESTROYING AlloyDB Infrastructure"
    log "=========================================="
    log_warning "Environment: $ENV"
    log_warning "This will DELETE:"
    log_warning "  - AlloyDB cluster (code-index-cluster-$ENV)"
    log_warning "  - AlloyDB instance (primary-instance-$ENV)"
    log_warning "  - VPC network and peering"
    log_warning "  - ALL DATABASE DATA WILL BE LOST!"
    echo ""

    AUTO_APPROVE=${TF_AUTO_APPROVE:-true}

    if [ "$AUTO_APPROVE" != "true" ]; then
        read -p "Type 'DELETE' to confirm destruction: " confirm
        if [ "$confirm" != "DELETE" ]; then
            log_info "Destruction cancelled"
            exit 0
        fi
    fi

    cd "$SCRIPT_DIR"

    log_info "Running terraform destroy..."
    if terraform destroy -auto-approve; then
        log "✅ Infrastructure destroyed successfully"
        log_info "All AlloyDB resources have been deleted"
        log_info "Billing for AlloyDB has stopped"
    else
        log_error "Infrastructure destruction failed"
        log_error "You may need to manually clean up resources"
        exit 1
    fi
}

plan_changes() {
    log "=========================================="
    log "  Terraform Plan"
    log "=========================================="
    log_info "Environment: $ENV"
    echo ""

    cd "$SCRIPT_DIR"
    terraform plan
}

show_outputs() {
    log "=========================================="
    log "  Terraform Outputs"
    log "=========================================="
    log_info "Environment: $ENV"
    echo ""

    cd "$SCRIPT_DIR"
    terraform output
}

validate_config() {
    log "=========================================="
    log "  Validating Terraform Configuration"
    log "=========================================="

    cd "$SCRIPT_DIR"

    if terraform validate; then
        log "✅ Configuration is valid"
    else
        log_error "Configuration validation failed"
        exit 1
    fi

    # Also run format check
    log_info "Checking formatting..."
    if terraform fmt -check -recursive; then
        log "✅ Formatting is correct"
    else
        log_warning "Formatting issues found. Run: terraform fmt -recursive"
    fi
}

check_status() {
    log "=========================================="
    log "  AlloyDB Cluster Status"
    log "=========================================="
    log_info "Environment: $ENV"
    echo ""

    local cluster_name="code-index-cluster-$ENV"

    log_info "Checking cluster: $cluster_name"

    if gcloud alloydb clusters describe "$cluster_name" \
        --region=us-east1 \
        --format=yaml 2>/dev/null; then

        log ""
        log "✅ Cluster exists and is accessible"

        # Get instance info
        log_info "Checking instance..."
        gcloud alloydb instances list \
            --cluster="$cluster_name" \
            --region=us-east1 \
            --format="table(name,state,instanceType,machineConfig.cpuCount)" 2>/dev/null || true
    else
        log_warning "Cluster not found or not accessible"
        log_info "Has it been deployed? Run: $0 apply $ENV"
    fi
}

# Main execution
main() {
    if [ -z "$OPERATION" ]; then
        usage
    fi

    case $OPERATION in
        apply)
            check_prerequisites
            init_terraform
            apply_infrastructure
            ;;
        destroy)
            check_prerequisites
            init_terraform
            destroy_infrastructure
            ;;
        plan)
            check_prerequisites
            init_terraform
            plan_changes
            ;;
        output)
            check_prerequisites
            show_outputs
            ;;
        validate)
            check_prerequisites
            init_terraform
            validate_config
            ;;
        status)
            check_prerequisites
            check_status
            ;;
        --help|-h)
            usage
            ;;
        *)
            log_error "Unknown operation: $OPERATION"
            usage
            ;;
    esac
}

main "$@"
