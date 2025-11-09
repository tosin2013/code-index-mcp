"""Automatic cleanup of idle projects from cloud storage.

This module implements the automatic cleanup functionality for removing
user projects that have been idle for a specified period. It's designed
to be triggered by Cloud Scheduler (GCP), EventBridge (AWS), or CronJob (OpenShift).

Cleanup Strategy:
- Scan cloud storage for user project directories
- Check last modified timestamp for each project
- Delete projects older than the specified threshold (default: 30 days)
- Log all cleanup actions for audit purposes
- Return detailed statistics about cleanup operations

ADR Reference: ADR 0002 - Automatic Resource Cleanup
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

# Logger for cleanup operations
logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of a cleanup operation.
    
    Attributes:
        scanned_count: Total number of projects scanned
        deleted_count: Number of projects deleted
        skipped_count: Number of projects skipped (below threshold)
        error_count: Number of errors encountered
        deleted_projects: List of deleted project identifiers
        errors: List of error messages
        execution_time_ms: Total execution time in milliseconds
    """
    scanned_count: int = 0
    deleted_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    deleted_projects: List[str] = None
    errors: List[str] = None
    execution_time_ms: float = 0.0
    
    def __post_init__(self):
        """Initialize list fields if None."""
        if self.deleted_projects is None:
            self.deleted_projects = []
        if self.errors is None:
            self.errors = []
    
    def to_dict(self) -> dict:
        """Convert result to dictionary for JSON serialization."""
        return {
            "scanned_count": self.scanned_count,
            "deleted_count": self.deleted_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "deleted_projects": self.deleted_projects,
            "errors": self.errors,
            "execution_time_ms": round(self.execution_time_ms, 2)
        }


def cleanup_idle_projects(
    max_idle_days: int = 30,
    dry_run: bool = False,
    bucket_name: Optional[str] = None
) -> CleanupResult:
    """Clean up idle projects from cloud storage.
    
    Scans the configured cloud storage bucket for user project directories
    and deletes any projects that have been idle (no modifications) for
    longer than the specified threshold.
    
    Args:
        max_idle_days: Maximum number of days a project can be idle before deletion.
                       Default is 30 days. Projects inactive longer than this will be deleted.
        dry_run: If True, only scan and report what would be deleted without actually deleting.
                 Useful for testing and validation. Default is False.
        bucket_name: Optional bucket name to override environment configuration.
                     If not provided, uses GCS_BUCKET_NAME from environment.
    
    Returns:
        CleanupResult: Detailed statistics about the cleanup operation including
                      counts of scanned, deleted, and skipped projects.
    
    Raises:
        ValueError: If bucket_name is not provided and GCS_BUCKET_NAME env var is not set.
        RuntimeError: If cleanup operation fails critically.
    
    Example:
        >>> # Dry run to see what would be deleted
        >>> result = cleanup_idle_projects(max_idle_days=30, dry_run=True)
        >>> print(f"Would delete {result.deleted_count} projects")
        
        >>> # Actual cleanup
        >>> result = cleanup_idle_projects(max_idle_days=30)
        >>> print(f"Deleted {result.deleted_count} idle projects")
    """
    start_time = datetime.now(timezone.utc)
    result = CleanupResult()
    
    # Get bucket name from parameter or environment
    bucket_name = bucket_name or os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        error_msg = "Bucket name not provided and GCS_BUCKET_NAME environment variable not set"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_idle_days)
    
    logger.info(
        f"Starting cleanup: bucket={bucket_name}, max_idle_days={max_idle_days}, "
        f"dry_run={dry_run}, cutoff_date={cutoff_date.isoformat()}"
    )
    
    try:
        # Import GCS client (lazy import to avoid dependency issues in non-GCP environments)
        try:
            from google.cloud import storage
        except ImportError:
            error_msg = "google-cloud-storage not installed. Install with: uv sync --extra gcp"
            logger.error(error_msg)
            result.error_count += 1
            result.errors.append(error_msg)
            return result
        
        # Initialize GCS client
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
        except Exception as e:
            error_msg = f"Failed to initialize GCS client: {str(e)}"
            logger.error(error_msg)
            result.error_count += 1
            result.errors.append(error_msg)
            return result
        
        # List all user directories (users/ prefix)
        # Structure: users/{user_id}/{project_name}/
        user_prefix = "users/"
        
        try:
            # Get all blobs with users/ prefix
            blobs = list(bucket.list_blobs(prefix=user_prefix, delimiter="/"))
            
            # Get user directories (prefixes after users/)
            user_dirs = set()
            for blob in blobs:
                # Extract user_id from path: users/{user_id}/...
                parts = blob.name.split("/")
                if len(parts) >= 2 and parts[0] == "users":
                    user_dirs.add(parts[1])  # user_id
            
            logger.info(f"Found {len(user_dirs)} user directories to scan")
            
            # Process each user's projects
            for user_id in user_dirs:
                user_prefix_path = f"{user_prefix}{user_id}/"
                
                # List all objects in this user's directory
                user_blobs = list(bucket.list_blobs(prefix=user_prefix_path))
                
                if not user_blobs:
                    logger.debug(f"No objects found for user: {user_id}")
                    continue
                
                # Find the most recent modification time for this user's projects
                most_recent = None
                for blob in user_blobs:
                    if blob.updated:
                        if most_recent is None or blob.updated > most_recent:
                            most_recent = blob.updated
                
                if most_recent is None:
                    logger.warning(f"No updated timestamp found for user: {user_id}")
                    result.skipped_count += 1
                    continue
                
                result.scanned_count += 1
                
                # Check if project is idle
                # Convert to UTC if not already
                if most_recent.tzinfo is None:
                    most_recent = most_recent.replace(tzinfo=timezone.utc)
                
                idle_days = (datetime.now(timezone.utc) - most_recent).days
                
                if most_recent < cutoff_date:
                    # Project is idle - delete it
                    logger.info(
                        f"Found idle project: user={user_id}, last_modified={most_recent.isoformat()}, "
                        f"idle_days={idle_days}, action={'DRY_RUN' if dry_run else 'DELETE'}"
                    )
                    
                    if not dry_run:
                        try:
                            # Delete all objects in this user's directory
                            deleted_count = 0
                            for blob in user_blobs:
                                blob.delete()
                                deleted_count += 1
                            
                            logger.info(
                                f"Deleted idle project: user={user_id}, files_deleted={deleted_count}"
                            )
                            result.deleted_count += 1
                            result.deleted_projects.append(f"{user_id} (idle {idle_days} days)")
                            
                        except Exception as e:
                            error_msg = f"Failed to delete project for user {user_id}: {str(e)}"
                            logger.error(error_msg)
                            result.error_count += 1
                            result.errors.append(error_msg)
                    else:
                        # Dry run - just count what would be deleted
                        result.deleted_count += 1
                        result.deleted_projects.append(f"{user_id} (idle {idle_days} days, DRY_RUN)")
                else:
                    # Project is still active
                    logger.debug(
                        f"Skipping active project: user={user_id}, last_modified={most_recent.isoformat()}, "
                        f"idle_days={idle_days}"
                    )
                    result.skipped_count += 1
        
        except Exception as e:
            error_msg = f"Error during cleanup scan: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.error_count += 1
            result.errors.append(error_msg)
    
    except Exception as e:
        error_msg = f"Critical error during cleanup: {str(e)}"
        logger.error(error_msg, exc_info=True)
        result.error_count += 1
        result.errors.append(error_msg)
        raise RuntimeError(error_msg) from e
    
    finally:
        # Calculate execution time
        end_time = datetime.now(timezone.utc)
        result.execution_time_ms = (end_time - start_time).total_seconds() * 1000
        
        logger.info(
            f"Cleanup complete: scanned={result.scanned_count}, "
            f"deleted={result.deleted_count}, skipped={result.skipped_count}, "
            f"errors={result.error_count}, execution_time={result.execution_time_ms:.2f}ms, "
            f"dry_run={dry_run}"
        )
    
    return result


def get_project_age_days(user_id: str, bucket_name: Optional[str] = None) -> Optional[int]:
    """Get the age (in days) of a user's project since last modification.
    
    Utility function to check how long a specific user's project has been idle.
    
    Args:
        user_id: The user identifier
        bucket_name: Optional bucket name (uses GCS_BUCKET_NAME env var if not provided)
    
    Returns:
        Number of days since last modification, or None if project not found
    
    Example:
        >>> age = get_project_age_days("john_doe")
        >>> print(f"Project is {age} days old")
    """
    bucket_name = bucket_name or os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        logger.error("Bucket name not provided and GCS_BUCKET_NAME environment variable not set")
        return None
    
    try:
        from google.cloud import storage
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # List all objects for this user
        user_prefix = f"users/{user_id}/"
        user_blobs = list(bucket.list_blobs(prefix=user_prefix))
        
        if not user_blobs:
            return None
        
        # Find most recent modification
        most_recent = None
        for blob in user_blobs:
            if blob.updated:
                if most_recent is None or blob.updated > most_recent:
                    most_recent = blob.updated
        
        if most_recent is None:
            return None
        
        # Ensure timezone-aware
        if most_recent.tzinfo is None:
            most_recent = most_recent.replace(tzinfo=timezone.utc)
        
        # Calculate age in days
        age = (datetime.now(timezone.utc) - most_recent).days
        return age
    
    except Exception as e:
        logger.error(f"Error getting project age for user {user_id}: {str(e)}")
        return None



