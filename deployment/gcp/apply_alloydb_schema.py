#!/usr/bin/env python3
"""
Apply AlloyDB Schema - Standalone Script

Usage:
  # From Cloud Shell or GCE VM with VPC access:
  python3 apply_alloydb_schema.py

  # Or specify connection string manually:
  python3 apply_alloydb_schema.py "postgresql://user:pass@host:5432/dbname"

Requirements:
  - psycopg2-binary (pip install psycopg2-binary)
  - Network access to AlloyDB (VPC access required)
  - Connection string from Secret Manager or as argument

Note: This script must run from an environment with VPC access to AlloyDB:
  - Google Cloud Shell (with VPC peering - NOT WORKING currently)
  - GCE VM in the same VPC ✅
  - Cloud Run Job with VPC connector ✅
  - Cloud Build with VPC connector ✅
"""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2


def get_connection_string_from_secret():
    """Fetch connection string from Google Secret Manager."""
    try:
        result = subprocess.run(
            [
                "gcloud",
                "secrets",
                "versions",
                "access",
                "latest",
                "--secret=alloydb-connection-string",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to fetch connection string from Secret Manager: {e}")
        print("   Make sure you're authenticated: gcloud auth login")
        return None


def apply_schema(connection_string, schema_file):
    """Apply schema to AlloyDB."""
    try:
        # Parse connection string
        parsed = urlparse(connection_string)

        print(f"🔌 Connecting to AlloyDB...")
        print(f"   Host: {parsed.hostname}")
        print(f"   Port: {parsed.port or 5432}")
        print(f"   Database: {parsed.path.lstrip('/')}")
        print(f"   User: {parsed.username}")
        print()

        # Connect to database
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password,
            connect_timeout=30,
        )

        print("✅ Connected successfully!")
        print()

        # Read schema file
        print(f"📖 Reading schema file: {schema_file}")
        with open(schema_file, "r") as f:
            schema_sql = f.read()

        print(f"   Schema size: {len(schema_sql):,} bytes")
        print()

        # Execute schema
        print("🚀 Applying schema...")
        cursor = conn.cursor()

        # Execute as a transaction
        try:
            cursor.execute(schema_sql)
            conn.commit()
            print("✅ Schema applied successfully!")
        except psycopg2.Error as e:
            conn.rollback()
            print(f"❌ Schema application failed: {e}")
            return False

        # Verify tables created
        print()
        print("🔍 Verifying tables...")
        cursor.execute(
            """
            SELECT table_name,
                   pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) as size
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """
        )
        tables = cursor.fetchall()

        if tables:
            print(f"\n✅ Found {len(tables)} tables:")
            for table_name, size in tables:
                print(f"   - {table_name:20s} ({size})")
        else:
            print("\n⚠️  No tables found")
            return False

        # Check for required tables
        required_tables = ["projects", "code_chunks", "users"]
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = ANY(%s);
        """,
            (required_tables,),
        )
        found_tables = [row[0] for row in cursor.fetchall()]

        print(f"\n🔍 Required tables check:")
        all_found = True
        for table in required_tables:
            if table in found_tables:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table} - MISSING")
                all_found = False

        # Check pgvector extension
        print(f"\n🔍 Checking pgvector extension:")
        cursor.execute(
            """
            SELECT extname, extversion
            FROM pg_extension
            WHERE extname = 'vector';
        """
        )
        vector_ext = cursor.fetchone()
        if vector_ext:
            print(f"   ✅ pgvector {vector_ext[1]} installed")
        else:
            print(f"   ❌ pgvector extension NOT installed")
            all_found = False

        # Count existing data
        print(f"\n📊 Data summary:")
        for table in required_tables:
            if table in found_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f"   - {table}: {count} rows")

        cursor.close()
        conn.close()

        # Summary
        print()
        if all_found:
            print("════════════════════════════════════════")
            print("✅ SCHEMA APPLICATION COMPLETE")
            print("════════════════════════════════════════")
            print()
            print("Next steps:")
            print("  1. Test semantic search: semantic_search_code()")
            print("  2. Ingest test repo: ingest_code_from_git()")
            print("  3. Run cloud tests: ansible-playbook test-cloud.yml")
            print()
            return True
        else:
            print("════════════════════════════════════════")
            print(f"⚠️  SCHEMA INCOMPLETE")
            print("════════════════════════════════════════")
            print(f"Found {len(found_tables)}/{len(required_tables)} required tables")
            print()
            return False

    except psycopg2.OperationalError as e:
        print(f"❌ Connection failed: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Verify you're running from an environment with VPC access")
        print("  2. Check AlloyDB instance is running: gcloud alloydb instances list")
        print(
            "  3. Verify connection string has correct IP: gcloud secrets versions access latest --secret=alloydb-connection-string"
        )
        print("  4. Test connectivity: nc -zv 10.22.0.2 5432")
        print()
        return False
    except FileNotFoundError:
        print(f"❌ Schema file not found: {schema_file}")
        print()
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    print("═══════════════════════════════════════════")
    print("  AlloyDB Schema Application")
    print("═══════════════════════════════════════════")
    print()

    # Determine schema file location
    script_dir = Path(__file__).parent
    schema_file = script_dir / "alloydb-schema.sql"

    if not schema_file.exists():
        print(f"❌ Schema file not found: {schema_file}")
        print(f"   Expected location: {schema_file.absolute()}")
        sys.exit(1)

    # Get connection string
    if len(sys.argv) > 1:
        # Connection string provided as argument
        connection_string = sys.argv[1]
        print("📝 Using connection string from command line argument")
        print()
    else:
        # Fetch from Secret Manager
        print("🔐 Fetching connection string from Secret Manager...")
        connection_string = get_connection_string_from_secret()
        if not connection_string:
            print()
            print("Usage:")
            print("  python3 apply_alloydb_schema.py [connection_string]")
            print()
            print("Examples:")
            print("  # From environment with gcloud auth:")
            print("  python3 apply_alloydb_schema.py")
            print()
            print("  # With explicit connection string:")
            print(
                "  python3 apply_alloydb_schema.py 'postgresql://user:pass@10.22.0.2:5432/code_index'"
            )
            print()
            sys.exit(1)
        print()

    # Apply schema
    success = apply_schema(connection_string, str(schema_file))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
