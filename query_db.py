#!/usr/bin/env python3
"""Quick script to query AlloyDB for documcp data"""

import os
import sys

# Add src to path
sys.path.insert(0, "src")

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary...")
    os.system("pip install psycopg2-binary")  # nosec
    import psycopg2

# Connection string
conn_string = os.getenv(
    "ALLOYDB_CONNECTION_STRING",
    "postgresql://code_index_admin:YOUR_PASSWORD_HERE@ALLOYDB_IP:5432/postgres",
)

print("=" * 60)
print("Querying AlloyDB for documcp data...")
print("=" * 60)
print()

try:
    # This will only work from Cloud Run or a VM in the VPC
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()

    # Check projects
    print("📊 Projects in database:")
    print("-" * 60)
    cursor.execute(
        """
        SELECT project_id, project_name, language, created_at
        FROM projects
        ORDER BY created_at DESC
    """
    )
    projects = cursor.fetchall()

    if projects:
        for project in projects:
            print(f"  - {project[1]} ({project[2]}) - Created: {project[3]}")
    else:
        print("  ❌ No projects found")

    print()

    # Check code chunks summary
    print("📦 Code chunks by project:")
    print("-" * 60)
    cursor.execute(
        """
        SELECT
            p.project_name,
            COUNT(*) as chunk_count,
            COUNT(DISTINCT c.file_path) as file_count,
            STRING_AGG(DISTINCT c.language, ', ') as languages
        FROM code_chunks c
        JOIN projects p ON c.project_id = p.project_id
        GROUP BY p.project_name
    """
    )
    chunks = cursor.fetchall()

    if chunks:
        for chunk in chunks:
            print(f"  - {chunk[0]}: {chunk[1]} chunks, {chunk[2]} files ({chunk[3]})")
    else:
        print("  ❌ No code chunks found")

    print()

    # Check for documcp specifically
    print("🔍 Searching for 'documcp' data:")
    print("-" * 60)
    cursor.execute(
        """
        SELECT
            c.file_path,
            c.function_name,
            c.language,
            LEFT(c.code, 150) as code_preview
        FROM code_chunks c
        JOIN projects p ON c.project_id = p.project_id
        WHERE p.project_name ILIKE '%documcp%'
        LIMIT 10
    """
    )
    documcp_chunks = cursor.fetchall()

    if documcp_chunks:
        print(f"  ✅ Found {len(documcp_chunks)} documcp chunks:")
        for chunk in documcp_chunks:
            print(f"\n  File: {chunk[0]}")
            print(f"  Function: {chunk[1]}")
            print(f"  Language: {chunk[2]}")
            print(f"  Preview: {chunk[3][:100]}...")
    else:
        print("  ❌ No documcp data found in database")
        print("  💡 You may need to run: ingest_code_for_search()")

    cursor.close()
    conn.close()

    print()
    print("=" * 60)
    print("✅ Query complete!")
    print("=" * 60)

except psycopg2.OperationalError as e:
    print()
    print("❌ Cannot connect to AlloyDB from this location")
    print()
    print("AlloyDB is on a private network and can only be accessed from:")
    print("  1. Cloud Run (already configured)")
    print("  2. A VM in the same VPC")
    print("  3. Via Cloud SQL Auth Proxy")
    print()
    print("To check data, either:")
    print("  - Test ingestion via Claude Desktop (it will show statistics)")
    print("  - Run this script from Cloud Run")
    print("  - Create a temporary VM in the VPC")
    print()
    print(f"Error: {e}")
    sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
