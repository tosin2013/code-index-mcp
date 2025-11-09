#!/bin/bash
# Test local PostgreSQL connection and schema

echo "🧪 Testing local PostgreSQL setup..."

# Connection string
export POSTGRES_CONNECTION="postgresql://code_index_admin:local_dev_password@localhost:5432/code_index"

# Test connection
echo "1. Testing connection..."
psql "$POSTGRES_CONNECTION" -c "SELECT version();" | head -5

# Verify extensions
echo ""
echo "2. Checking extensions..."
psql "$POSTGRES_CONNECTION" -c "SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp');"

# Check tables
echo ""
echo "3. Verifying tables..."
psql "$POSTGRES_CONNECTION" -c "\dt"

# Check functions
echo ""
echo "4. Checking semantic search function..."
psql "$POSTGRES_CONNECTION" -c "\df semantic_search_code"

# Get test user
echo ""
echo "5. Test user:"
psql "$POSTGRES_CONNECTION" -c "SELECT user_id, email FROM users WHERE email = 'dev@localhost';"

echo ""
echo "✅ Local PostgreSQL is ready for testing!"
echo ""
echo "Connection string:"
echo "  $POSTGRES_CONNECTION"
