# AlloyDB Development Instance Configuration
# Cost: ~$100/month (1 vCPU, 8 GB RAM, 10 GB storage)
#
# Deploy with:
#   cd deployment/gcp
#   terraform init
#   terraform plan -var="project_id=YOUR_PROJECT_ID"
#   terraform apply -var="project_id=YOUR_PROJECT_ID"

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-east1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# VPC Network for AlloyDB
resource "google_compute_network" "alloydb_network" {
  name                    = "code-index-alloydb-network-${var.environment}"
  auto_create_subnetworks = false
}

# Subnet for AlloyDB
resource "google_compute_subnetwork" "alloydb_subnet" {
  name          = "code-index-alloydb-subnet-${var.environment}"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.alloydb_network.id
}

# Private Service Connection for AlloyDB
resource "google_compute_global_address" "alloydb_private_ip" {
  name          = "code-index-alloydb-ip-${var.environment}"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.alloydb_network.id
}

resource "google_service_networking_connection" "alloydb_connection" {
  network                 = google_compute_network.alloydb_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.alloydb_private_ip.name]
}

# AlloyDB Cluster
resource "google_alloydb_cluster" "code_index_cluster" {
  cluster_id = "code-index-cluster-${var.environment}"
  location   = var.region

  network_config {
    network = google_compute_network.alloydb_network.id
  }

  # Development configuration
  initial_user {
    user     = "code_index_admin"
    password = random_password.alloydb_password.result
  }

  # Automated backups
  automated_backup_policy {
    enabled       = true
    backup_window = "3600s" # 1 hour backup window
    location      = var.region

    weekly_schedule {
      days_of_week = ["MONDAY", "WEDNESDAY", "FRIDAY"]
      start_times {
        hours   = 2
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }

    quantity_based_retention {
      count = 7 # Keep 7 backups
    }
  }

  depends_on = [google_service_networking_connection.alloydb_connection]
}

# Generate secure random password
resource "random_password" "alloydb_password" {
  length  = 32
  special = true
}

# AlloyDB Primary Instance (Development size)
resource "google_alloydb_instance" "primary" {
  cluster       = google_alloydb_cluster.code_index_cluster.name
  instance_id   = "code-index-primary-${var.environment}"
  instance_type = "PRIMARY"

  # Development configuration: 2 vCPU, 16 GB RAM (minimum allowed)
  machine_config {
    cpu_count = 2
  }

  # Availability type (ZONAL for dev, REGIONAL for prod)
  availability_type = "ZONAL"

  # Enable query insights
  query_insights_config {
    query_string_length     = 1024
    record_application_tags = true
    record_client_address   = true
  }
}

# Store password in Secret Manager
resource "google_secret_manager_secret" "alloydb_password" {
  secret_id = "alloydb-password-${var.environment}"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "alloydb_password" {
  secret      = google_secret_manager_secret.alloydb_password.id
  secret_data = random_password.alloydb_password.result
}

# VPC Connector for Cloud Run to access AlloyDB
resource "google_vpc_access_connector" "connector" {
  name          = "alloydb-connector"
  region        = var.region
  network       = google_compute_network.alloydb_network.name
  ip_cidr_range = "10.8.0.0/28"
}

# Outputs
output "cluster_name" {
  value       = google_alloydb_cluster.code_index_cluster.name
  description = "AlloyDB cluster name"
}

output "primary_instance_name" {
  value       = google_alloydb_instance.primary.name
  description = "AlloyDB primary instance name"
}

output "primary_instance_ip" {
  value       = google_alloydb_instance.primary.ip_address
  description = "AlloyDB primary instance private IP"
  sensitive   = true
}

output "database_password_secret" {
  value       = google_secret_manager_secret.alloydb_password.name
  description = "Secret Manager secret name for database password"
}

output "vpc_connector_name" {
  value       = google_vpc_access_connector.connector.name
  description = "VPC connector name for Cloud Run"
}

output "connection_string" {
  value       = "postgresql://code_index_admin:[PASSWORD]@${google_alloydb_instance.primary.ip_address}:5432/postgres"
  description = "Database connection string (retrieve password from Secret Manager)"
  sensitive   = true
}

# Cost estimate output
output "estimated_monthly_cost" {
  value = <<-EOT
    Development AlloyDB Configuration Cost Estimate:

    - AlloyDB Instance (2 vCPU, 16 GB): ~$164/month (minimum allowed)
    - Storage (10 GB SSD): ~$2/month
    - Backups (7 daily): ~$1/month
    - VPC Connector: ~$7/month
    - Network Egress: ~$5/month (estimated)

    Total: ~$179-185/month

    Note: Scale to production (4 vCPU, 32 GB, 100 GB) = ~$340/month
  EOT
}
