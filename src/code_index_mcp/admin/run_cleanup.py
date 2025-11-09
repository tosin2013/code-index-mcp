#!/usr/bin/env python3
"""Standalone cleanup script for Cloud Scheduler integration.

This script is designed to be run as a Cloud Run Job, triggered by
Cloud Scheduler (GCP), EventBridge (AWS), or CronJob (OpenShift).

Usage:
    python run_cleanup.py [--max-idle-days DAYS] [--dry-run] [--bucket BUCKET_NAME]

Examples:
    # Dry run to see what would be deleted
    python run_cleanup.py --dry-run
    
    # Delete projects idle for more than 30 days
    python run_cleanup.py --max-idle-days 30
    
    # Specify custom bucket
    python run_cleanup.py --bucket my-bucket-name

Environment Variables:
    GCS_BUCKET_NAME: Default bucket name if --bucket not provided
    GOOGLE_APPLICATION_CREDENTIALS: Path to service account key (for local testing)

ADR Reference: ADR 0002 - Automatic Resource Cleanup
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add src to path for local development
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from code_index_mcp.admin import cleanup_idle_projects

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description='Clean up idle projects from cloud storage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--max-idle-days',
        type=int,
        default=30,
        help='Maximum number of days a project can be idle before deletion (default: 30)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (only report what would be deleted, do not delete)'
    )
    
    parser.add_argument(
        '--bucket',
        type=str,
        default=None,
        help='Bucket name (overrides GCS_BUCKET_NAME environment variable)'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format for programmatic processing'
    )
    
    args = parser.parse_args()
    
    logger.info(f"Starting cleanup script: max_idle_days={args.max_idle_days}, dry_run={args.dry_run}")
    
    try:
        # Run cleanup
        result = cleanup_idle_projects(
            max_idle_days=args.max_idle_days,
            dry_run=args.dry_run,
            bucket_name=args.bucket
        )
        
        # Output results
        if args.json:
            # JSON output for programmatic processing
            output = {
                "status": "success",
                "cleanup_result": result.to_dict()
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            print("\n" + "=" * 60)
            print(f"Cleanup {'Dry Run ' if args.dry_run else ''}Complete")
            print("=" * 60)
            print(f"Scanned:  {result.scanned_count} projects")
            print(f"Deleted:  {result.deleted_count} projects")
            print(f"Skipped:  {result.skipped_count} projects (still active)")
            print(f"Errors:   {result.error_count}")
            print(f"Duration: {result.execution_time_ms:.2f} ms")
            
            if result.deleted_projects:
                print(f"\nDeleted projects:")
                for project in result.deleted_projects:
                    print(f"  - {project}")
            
            if result.errors:
                print(f"\nErrors encountered:")
                for error in result.errors:
                    print(f"  - {error}")
            
            print("=" * 60)
        
        # Exit with success
        logger.info(f"Cleanup script completed successfully: {result.deleted_count} projects deleted")
        sys.exit(0)
        
    except ValueError as e:
        # Configuration error
        logger.error(f"Configuration error: {str(e)}")
        if args.json:
            print(json.dumps({
                "status": "error",
                "error_type": "configuration",
                "message": str(e)
            }, indent=2))
        else:
            print(f"\nERROR: {str(e)}", file=sys.stderr)
            print("\nPlease set GCS_BUCKET_NAME environment variable or use --bucket option.", file=sys.stderr)
        sys.exit(1)
        
    except Exception as e:
        # Unexpected error
        logger.error(f"Cleanup script failed: {str(e)}", exc_info=True)
        if args.json:
            print(json.dumps({
                "status": "error",
                "error_type": "runtime",
                "message": str(e)
            }, indent=2))
        else:
            print(f"\nFATAL ERROR: {str(e)}", file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()



