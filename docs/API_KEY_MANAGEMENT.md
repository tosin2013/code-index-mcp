# API Key Management Guide

**For Administrators & Power Users**

This guide explains how to generate, manage, and revoke API keys for Code Index MCP on Google Cloud Run.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Generating API Keys](#generating-api-keys)
4. [Listing API Keys](#listing-api-keys)
5. [Revoking API Keys](#revoking-api-keys)
6. [Permissions](#permissions)
7. [Security Best Practices](#security-best-practices)
8. [Troubleshooting](#troubleshooting)

---

## 🔍 Overview

### API Key Format

API keys follow this format:
```
ci_<user_id>_<random_secret>
```

**Example**: `ci_alice_dev_abc123def456789`

**Components**:
- **Prefix**: `ci_` (Code Index identifier)
- **User ID**: Letters, numbers, underscores only (e.g., `alice_dev`)
- **Secret**: 32-character random alphanumeric string

### Storage

API keys are stored in **Google Secret Manager** as:
```
projects/{project_id}/secrets/mcp-api-key-{user_id}
```

---

## ✅ Prerequisites

1. **Google Cloud CLI** (`gcloud`) installed and authenticated
2. **Project access** with these permissions:
   - `secretmanager.secrets.create`
   - `secretmanager.secrets.get`
   - `secretmanager.secrets.list`
   - `secretmanager.versions.add`
   - `secretmanager.versions.access`
3. **Correct project** set:
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```

---

## 🔑 Generating API Keys

### Basic Usage

```bash
cd deployment/gcp
./setup-secrets.sh <user_id> <permissions>
```

### Examples

**1. Generate key for developer (read & write)**:
```bash
./setup-secrets.sh alice_dev read,write
```

**Output**:
```
========================================
  MCP API Key Setup
========================================

[SUCCESS] API Key generated successfully!

User:        alice_dev
API Key:     ci_alice_dev_abc123def456789xyz...
Permissions: read,write
Secret:      mcp-api-key-alice-dev

Service URL: https://code-index-mcp-dev-xxxxx.run.app/sse

[INFO] Configuration for MCP client:
{
  "url": "https://code-index-mcp-dev-xxxxx.run.app/sse",
  "transport": "sse",
  "headers": {
    "X-API-Key": "ci_alice_dev_abc123def456789xyz..."
  }
}
```

**2. Generate key for read-only user**:
```bash
./setup-secrets.sh bob_viewer read
```

**3. Generate key for CI/CD**:
```bash
./setup-secrets.sh github_actions read
```

### User ID Requirements

✅ **Valid**:
- `alice` - Letters only
- `alice_dev` - Letters and underscores
- `user123` - Letters and numbers
- `team_member_01` - Combined format

❌ **Invalid**:
- `alice-dev` - Contains hyphen
- `alice.dev` - Contains period
- `alice dev` - Contains space
- `alice@dev` - Contains special character

---

## 📋 Listing API Keys

### List All Keys

```bash
gcloud secrets list \
  --filter="name:mcp-api-key-*" \
  --format="table(name, createTime)" \
  --project=YOUR_PROJECT_ID
```

**Output**:
```
NAME                          CREATE_TIME
mcp-api-key-alice-dev         2025-10-25T10:00:00Z
mcp-api-key-bob-viewer        2025-10-25T11:30:00Z
mcp-api-key-github-actions    2025-10-25T12:00:00Z
```

### View Key Details

```bash
gcloud secrets describe mcp-api-key-alice-dev \
  --project=YOUR_PROJECT_ID
```

**Output**:
```
createTime: '2025-10-25T10:00:00.000Z'
labels:
  permissions: read,write
  user: alice_dev
name: projects/YOUR_PROJECT_ID/secrets/mcp-api-key-alice-dev
replication:
  automatic: {}
```

### Retrieve API Key Value

```bash
gcloud secrets versions access latest \
  --secret=mcp-api-key-alice-dev \
  --project=YOUR_PROJECT_ID
```

⚠️ **Warning**: This reveals the actual API key. Use with caution.

---

## 🗑️ Revoking API Keys

### Delete a Secret

```bash
gcloud secrets delete mcp-api-key-<user_id> \
  --project=YOUR_PROJECT_ID
```

**Example**:
```bash
gcloud secrets delete mcp-api-key-alice-dev \
  --project=YOUR_PROJECT_ID
```

**Confirmation**:
```
You are about to delete secret [mcp-api-key-alice-dev]

Do you want to continue (Y/n)? Y

Deleted secret [mcp-api-key-alice-dev].
```

### Disable a Secret (Soft Delete)

```bash
gcloud secrets versions disable latest \
  --secret=mcp-api-key-<user_id> \
  --project=YOUR_PROJECT_ID
```

This keeps the secret but prevents access.

### Re-enable a Secret

```bash
gcloud secrets versions enable <version_id> \
  --secret=mcp-api-key-<user_id> \
  --project=YOUR_PROJECT_ID
```

---

## 🔐 Permissions

API keys support two permission levels:

### `read` Permission
- ✅ Search code
- ✅ Read files
- ✅ List directories
- ✅ Get symbol information
- ❌ Write files
- ❌ Modify project settings

**Use Case**: Viewers, CI/CD read-only jobs, auditors

### `read,write` Permission
- ✅ All read permissions
- ✅ Write files
- ✅ Modify project settings
- ✅ Refresh index
- ✅ Manage file watchers

**Use Case**: Developers, administrators, build systems

### Future Permissions (Coming Soon)
- `admin` - Manage API keys, view all users
- `read,write,execute` - Run code analysis tools
- `read,write,delete` - Delete files and projects

---

## 🛡️ Security Best Practices

### For Administrators

1. **Generate unique keys per user**
   - ❌ Don't share a single key among multiple users
   - ✅ Create individual keys for each team member

2. **Use descriptive user IDs**
   ```bash
   # Good
   ./setup-secrets.sh alice_prod read,write
   ./setup-secrets.sh bob_dev read
   ./setup-secrets.sh github_ci read
   
   # Bad (too generic)
   ./setup-secrets.sh user1 read,write
   ./setup-secrets.sh temp read,write
   ```

3. **Audit key usage regularly**
   ```bash
   # List all keys
   gcloud secrets list --filter="name:mcp-api-key-*"
   
   # Check last access time
   gcloud logging read "resource.labels.secret_id:mcp-api-key-*" \
     --format="table(timestamp, resource.labels.secret_id)"
   ```

4. **Rotate keys periodically**
   - Regenerate keys every 90 days
   - Revoke old keys after transition period
   - Notify users before rotation

5. **Monitor for suspicious activity**
   ```bash
   # Check failed authentication attempts
   gcloud logging read \
     "resource.type=cloud_run_revision AND textPayload:\"Authentication failed\"" \
     --limit=50
   ```

### For Users

1. **Never commit API keys to Git**
   ```bash
   # Check if key is in git
   git log -S "ci_" --all
   ```

2. **Store keys securely**
   - ✅ In MCP client config (encrypted)
   - ✅ In environment variables (for CI/CD)
   - ✅ In secrets manager (for production)
   - ❌ In plain text files
   - ❌ In shared documents
   - ❌ In chat messages

3. **Revoke compromised keys immediately**
   ```bash
   # If you accidentally commit a key
   gcloud secrets delete mcp-api-key-<your_user_id>
   # Then generate a new one
   ./setup-secrets.sh <your_user_id> read,write
   ```

4. **Use read-only keys when possible**
   - For viewing code only, use `read` permission
   - Request `write` permission only when needed

---

## 🚨 Troubleshooting

### "Permission denied" when generating keys

**Cause**: Missing IAM permissions

**Solution**:
```bash
# Check your permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:$(gcloud config get-value account)"

# Request these roles from admin:
# - roles/secretmanager.admin
# - roles/secretmanager.secretAccessor
```

### "Secret already exists"

**Cause**: Trying to create a key for an existing user

**Solution**:
```bash
# Option 1: Delete the old secret first
gcloud secrets delete mcp-api-key-<user_id>

# Option 2: Use a different user ID
./setup-secrets.sh alice_dev2 read,write
```

### "Invalid user_id format"

**Cause**: User ID contains invalid characters

**Solution**:
```bash
# Bad: alice-dev (contains hyphen)
# Good: alice_dev (underscore is OK)

./setup-secrets.sh alice_dev read,write
```

### Cannot retrieve API key value

**Cause**: Missing `secretmanager.versions.access` permission

**Solution**:
```bash
# Grant yourself access
gcloud secrets add-iam-policy-binding mcp-api-key-<user_id> \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 📊 Key Lifecycle

```
┌─────────────┐
│   Create    │  ./setup-secrets.sh user_id read,write
└──────┬──────┘
       │
       v
┌─────────────┐
│   Active    │  User accesses API with key
└──────┬──────┘
       │
       ├──> [Rotate] ──> Create new key, revoke old
       │
       ├──> [Disable] ──> Soft delete (can re-enable)
       │
       v
┌─────────────┐
│   Revoked   │  gcloud secrets delete
└─────────────┘
```

---

## 🔄 Batch Operations

### Generate Keys for Multiple Users

```bash
#!/bin/bash
# generate-team-keys.sh

USERS=(
  "alice:read,write"
  "bob:read"
  "charlie:read,write"
  "ci_deploy:read"
)

for user_perm in "${USERS[@]}"; do
  IFS=":" read -r user perms <<< "$user_perm"
  echo "Generating key for $user with permissions: $perms"
  ./setup-secrets.sh "$user" "$perms"
  echo "---"
done
```

### Revoke Multiple Keys

```bash
#!/bin/bash
# revoke-team-keys.sh

USERS=("alice" "bob" "charlie")

for user in "${USERS[@]}"; do
  echo "Revoking key for $user"
  gcloud secrets delete "mcp-api-key-$user" --quiet
done
```

---

## 📚 Related Documentation

- [User Onboarding Guide](USER_ONBOARDING_GUIDE.md) - For end users
- [Deployment Guide](DEPLOYMENT.md) - Cloud deployment instructions
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) - Common issues

---

**Last Updated**: October 25, 2025  
**Version**: 2.4.1 (Phase 2A)  
**Deployment**: Google Cloud Run



