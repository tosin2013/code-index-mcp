#!/bin/bash
# Apply AlloyDB schema via Cloud Shell (has VPC access to AlloyDB)

set -e

PROJECT_ID="${1:-tosinscloud}"
ENV_NAME="${2:-dev}"
REGION="${3:-us-east1}"
SCHEMA_FILE="${4:-/tmp/alloydb-schema.sql}"

echo "========================================"
echo "  Apply AlloyDB Schema via Cloud Shell"
echo "========================================"
echo "Project: $PROJECT_ID"
echo "Environment: $ENV_NAME"
echo "Region: $REGION"
echo ""

# Install psycopg2 if not available
echo "📦 Installing dependencies..."
pip3 install --quiet --user psycopg2-binary

# Get connection string from Secret Manager
echo "🔐 Fetching connection string..."
CONNECTION_STRING=$(gcloud secrets versions access latest \
  --secret=alloydb-connection-string \
  --project=$PROJECT_ID \
  --verbosity=error)

# Create Python script for schema application
cat > /tmp/apply_schema.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""Apply AlloyDB schema from SQL file."""
import sys
import psycopg2
from urllib.parse import urlparse

def apply_schema(connection_string, schema_file):
    """Apply schema to AlloyDB."""
    try:
        # Parse connection string
        parsed = urlparse(connection_string)

        print(f"🔌 Connecting to AlloyDB...")
        print(f"   Host: {parsed.hostname}")
        print(f"   Database: {parsed.path.lstrip('/')}")
        print(f"   User: {parsed.username}")

        # Connect to database
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password,
            connect_timeout=30
        )

        print("✅ Connected successfully!")

        # Read schema file
        print(f"\n📖 Reading schema file: {schema_file}")
        with open(schema_file, 'r') as f:
            schema_sql = f.read()

        print(f"   Schema size: {len(schema_sql)} bytes")

        # Execute schema
        print("\n🚀 Applying schema...")
        cursor = conn.cursor()
        cursor.execute(schema_sql)
        conn.commit()

        print("✅ Schema applied successfully!")

        # Verify tables created
        print("\n🔍 Verifying tables...")
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()

        if tables:
            print(f"\n✅ Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table[0]}")
        else:
            print("\n⚠️  No tables found")

        # Check for required tables
        required_tables = ['projects', 'code_chunks', 'users']
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = ANY(%s);
        """, (required_tables,))
        found_tables = [row[0] for row in cursor.fetchall()]

        print(f"\n🔍 Required tables check:")
        for table in required_tables:
            if table in found_tables:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table} - MISSING")

        cursor.close()
        conn.close()

        # Summary
        if len(found_tables) == len(required_tables):
            print("\n✅ SCHEMA APPLICATION COMPLETE")
            return 0
        else:
            print(f"\n⚠️  SCHEMA INCOMPLETE: {len(found_tables)}/{len(required_tables)} required tables")
            return 1

    except psycopg2.OperationalError as e:
        print(f"❌ Connection failed: {e}")
        return 2
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 3

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: apply_schema.py <connection_string> <schema_file>")
        sys.exit(1)

    connection_string = sys.argv[1]
    schema_file = sys.argv[2]
    sys.exit(apply_schema(connection_string, schema_file))
PYTHON_SCRIPT

# Make script executable
chmod +x /tmp/apply_schema.py

# Apply schema
echo ""
echo "🚀 Applying schema to AlloyDB..."
python3 /tmp/apply_schema.py "$CONNECTION_STRING" "$SCHEMA_FILE"
RESULT=$?

# Cleanup
rm -f /tmp/apply_schema.py

if [ $RESULT -eq 0 ]; then
    echo ""
    echo "════════════════════════════════════════"
    echo "✅ AlloyDB Schema Application Complete"
    echo "════════════════════════════════════════"
    echo ""
    exit 0
else
    echo ""
    echo "❌ Schema application failed with exit code $RESULT"
    echo ""
    exit $RESULT
fi
