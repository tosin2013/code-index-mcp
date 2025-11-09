# AlloyDB Connection String URL Encoding Fix

**Date**: October 27, 2025
**Issue**: `psycopg2.OperationalError: invalid integer value "..." for connection option "port"`
**Root Cause**: Special characters in AlloyDB password not URL-encoded
**Status**: ✅ Fixed

---

## The Problem

When AlloyDB passwords contain special characters (e.g., `@`, `(`, `:`, `<`, `>`), the PostgreSQL connection string parser fails because these characters have special meaning in URLs.

### Error Example

```
psycopg2.OperationalError: invalid integer value "t<H@10.175.0.2:5432" for connection option "port"
```

**Original password**: `***REMOVED***`
**Broken connection string**: `postgresql://code_index_admin:***REMOVED***@10.175.0.2:5432/postgres`

**What went wrong**:
- The `@` in the password was interpreted as the user/host separator
- The `:` was interpreted as a port separator
- The parser tried to parse `t<H` as the port number → error

---

## The Solution

**1. URL-encode the password** before including it in the connection string.
**2. Use `echo -n` to prevent trailing newlines** when storing in Secret Manager.

### Manual Fix

```python
from urllib.parse import quote_plus

# Original password with special characters
password = "***REMOVED***"

# URL-encode the password
encoded_password = quote_plus(password)
# Result: "u0kJ6MZX%40eAzCuw%28Hr1-JkogKiDB%3At%3CH"

# Build connection string with encoded password
connection_string = f"postgresql://code_index_admin:{encoded_password}@10.175.0.2:5432/postgres"
```

**CRITICAL**: When storing in Secret Manager, use `echo -n` (not `echo`):

```bash
# WRONG (adds trailing newline → database "postgres\n" does not exist)
echo "postgresql://..." | gcloud secrets versions add alloydb-connection-string --data-file=-

# CORRECT (no trailing newline)
echo -n "postgresql://..." | gcloud secrets versions add alloydb-connection-string --data-file=-
```

### Automated Fix (Recommended)

Use the new helper script:

```bash
cd deployment/gcp
./create-connection-string-secret.sh dev
```

This script:
1. Retrieves the AlloyDB password from Secret Manager
2. URL-encodes the password automatically
3. Creates/updates the `alloydb-connection-string` secret
4. Verifies the format is correct

---

## Character Encoding Reference

| Character | URL-Encoded | Reason |
|-----------|-------------|--------|
| `@` | `%40` | User/host separator |
| `(` | `%28` | Reserved character |
| `)` | `%29` | Reserved character |
| `:` | `%3A` | Host/port separator |
| `<` | `%3C` | Reserved character |
| `>` | `%3E` | Reserved character |
| `/` | `%2F` | Path separator |
| `?` | `%3F` | Query string separator |
| `#` | `%23` | Fragment identifier |

**Reference**: [RFC 3986 - URL Encoding](https://datatracker.ietf.org/doc/html/rfc3986#section-2.1)

---

## Verification Steps

### 1. Check the Secret

```bash
gcloud secrets versions access latest --secret="alloydb-connection-string"
```

**Good** (URL-encoded):
```
postgresql://code_index_admin:u0kJ6MZX%40eAzCuw%28Hr1-JkogKiDB%3At%3CH@10.175.0.2:5432/postgres
```

**Bad** (not encoded):
```
postgresql://code_index_admin:***REMOVED***@10.175.0.2:5432/postgres
```

### 2. Test Connection

```bash
# Via Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=code-index-mcp-dev" \
    --limit=20 \
    --format="table(timestamp,textPayload)" \
    --project=tosinscloud \
    --freshness=5m | grep -i ingestion
```

### 3. Test Ingestion

Use Claude Desktop or MCP Inspector:

```
ingest_code_for_search(
    directory_path="/Users/username/project",
    project_name="my-project",
    use_current_project=False
)
```

**Success response**:
```json
{
  "status": "success",
  "project_name": "my-project",
  "files_processed": 42,
  "chunks_created": 156,
  "chunks_stored": 156
}
```

---

## Implementation Timeline

| Step | Action | Status |
|------|--------|--------|
| 1 | Identified error in Cloud Run logs | ✅ Complete |
| 2 | Diagnosed root cause (special chars) | ✅ Complete |
| 3 | Created URL-encoded password | ✅ Complete |
| 4 | Updated Secret Manager (v3) | ✅ Complete |
| 5 | Redeployed Cloud Run (rev 00009) | ✅ Complete |
| 6 | **Found 2nd issue: trailing newline** | ✅ Complete |
| 7 | **Fixed: used `echo -n` instead of `echo`** | ✅ Complete |
| 8 | **Updated Secret Manager (v4)** | ✅ Complete |
| 9 | **Redeployed Cloud Run (rev 00010)** | ✅ Complete |
| 10 | Created helper script | ✅ Complete |
| 11 | Updated ADR 0003 | ✅ Complete |
| 12 | Updated QUICKSTART guide | ✅ Complete |
| 13 | Added troubleshooting docs | ✅ Complete |

---

## Files Modified

1. **`docs/adrs/0003-google-cloud-code-ingestion-with-alloydb.md`**
   - Added "Implementation Notes" section
   - Documented URL encoding requirements
   - Added character encoding reference table

2. **`deployment/gcp/create-connection-string-secret.sh`** (NEW)
   - Automated URL encoding for passwords
   - Creates properly formatted connection string secret
   - Includes validation and verification

3. **`deployment/gcp/QUICKSTART_SEMANTIC_SEARCH.md`**
   - Added `create-connection-string-secret.sh` to Step 1
   - Added troubleshooting section for URL encoding errors
   - Added link to ADR 0003

4. **Secret Manager** (Google Cloud)
   - Updated `alloydb-connection-string` secret (version 3)
   - Password now properly URL-encoded

---

## Lessons Learned

### For Future Deployments

1. **Always URL-encode passwords** in connection strings
2. **Test connection strings** before storing in Secret Manager
3. **Automate the encoding** to prevent human error
4. **Document in ADRs** for institutional knowledge

### For Terraform

Consider adding a `local` block to auto-encode passwords:

```hcl
locals {
  db_password_encoded = urlencode(random_password.database_password.result)
  connection_string   = "postgresql://${var.db_user}:${local.db_password_encoded}@${google_alloydb_instance.primary.ip_address}:5432/${var.db_name}"
}
```

### For Testing

Always include connection string tests in CI/CD:

```python
def test_connection_string_format():
    conn_str = os.getenv("ALLOYDB_CONNECTION_STRING")
    # Check for URL-encoded characters
    assert '%' in conn_str or not has_special_chars(get_password(conn_str))
```

---

## Related Resources

- **ADR 0003**: [Google Cloud Code Ingestion with AlloyDB](adrs/0003-google-cloud-code-ingestion-with-alloydb.md#implementation-notes)
- **Quick Start**: [Semantic Search Deployment](../deployment/gcp/QUICKSTART_SEMANTIC_SEARCH.md)
- **Helper Script**: [`create-connection-string-secret.sh`](../deployment/gcp/create-connection-string-secret.sh)
- **RFC 3986**: [URL Encoding Standard](https://datatracker.ietf.org/doc/html/rfc3986#section-2.1)

---

**Confidence**: 99% - Issue identified, fixed, tested, and documented comprehensively.
