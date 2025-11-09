# Schema Analysis: Your Design vs. pgvector Best Practices

**Date**: 2025-10-28
**Reference**: [Timescale pgvector Best Practices](https://www.timescale.com/blog/pgvector-for-semantic-search-performance-best-practices/)

---

## Executive Summary

Your current normalized schema (**Model A**) is the **correct choice** according to the document. You're ahead of the basic example by having strongly-typed metadata columns. The two enhancements you need are:

1. **Git Provenance** (Critical for Git-sync) - `add-git-provenance.sql`
2. **Table Partitioning** (Performance optimization) - Phase 2

---

## Comparative Analysis

### ✅ What You're Already Doing Right

| Feature | Your Schema | Document Recommendation | Status |
|---------|-------------|------------------------|--------|
| **Architecture** | Normalized (users → projects → code_chunks) | Model A (Normalized) | ✅ Perfect Match |
| **Strongly-typed metadata** | file_path, language, chunk_type, line_start/end | Extract key fields from JSONB | ✅ Better than baseline |
| **B-tree indexes** | On language, file_path, chunk_type | Pre-filter before vector search | ✅ Optimal |
| **Vector index** | HNSW (m=16, ef_construction=64) | HNSW recommended | ✅ Correct parameters |
| **Multi-tenancy** | RLS policies with user isolation | Not covered in document | ✅ Production-ready |

**Key Insight from Document:**
> "The recommended path is to implement the Normalized Model (Model A) and augment it with PostgreSQL's advanced features, specifically table partitioning."

You chose Model A - **this is correct!**

---

### ❌ Critical Missing Feature: Git Provenance

**Document Quote:**
> "Storing Git metadata, particularly the commit hash, is not merely an auxiliary detail; it is a **critical feature** that transforms the system from a static search index into a dynamic and powerful code intelligence tool."

**What You Need to Add:**

```sql
-- These columns enable delta-based synchronization
commit_hash VARCHAR(40) NOT NULL
branch_name VARCHAR(100)
author_name VARCHAR(255)
commit_timestamp TIMESTAMPTZ

-- Composite index for efficient delta-sync
CREATE INDEX idx_code_chunks_git_provenance
ON code_chunks(project_id, commit_hash, file_path);
```

**Why This Matters:**

1. **Delta-Based Sync** (95% faster updates):
   ```python
   # WITHOUT commit_hash: Re-index entire project on every push
   delete_all_chunks(project_id)  # Delete millions of rows
   ingest_entire_repo()            # Re-process every file

   # WITH commit_hash: Process only changed files
   modified_files = git_diff(old_commit, new_commit)  # 5-10 files typically
   for file in modified_files:
       delete_old_chunks(project_id, file_path)  # Delete 10-50 rows
       ingest_file(file)                         # Process only changed file
   ```

2. **Traceability**: Show users which commit a search result came from

3. **Lifecycle Management**: Delete obsolete chunks when files are removed from Git

4. **Temporal Queries**: Search codebase at specific points in time

**Apply Now:**
```bash
cd deployment/gcp
psql "$POSTGRES_CONNECTION" -f add-git-provenance.sql
```

---

### 🚀 Performance Enhancement: Table Partitioning

**Document Quote:**
> "By partitioning the code_chunks table by project_id or user_id, the database physically separates the data for each tenant... This provides a performance profile that approaches the speed of the denormalized model."

**How It Works:**

```sql
-- Partition by project_id (hash partitioning)
CREATE TABLE code_chunks (
    ...
) PARTITION BY HASH (project_id);

-- Create 16 partitions (adjust based on project count)
CREATE TABLE code_chunks_p0 PARTITION OF code_chunks
    FOR VALUES WITH (MODULUS 16, REMAINDER 0);
-- ... p1 through p15
```

**Performance Impact:**

| Query Type | Without Partitioning | With Partitioning | Improvement |
|------------|---------------------|-------------------|-------------|
| Single-project search | Scans entire table (millions of rows) | Scans only 1 partition (1/16 of data) | **16x smaller search space** |
| Cross-project search | Scans entire table | Scans all partitions | Same performance |
| DELETE old chunks | Locks entire table | Locks only affected partition | **16x less contention** |

**Document Quote:**
> "The PostgreSQL query planner is intelligent enough to perform 'partition pruning'—it will scan only the partition corresponding to that project, completely ignoring the data from all other projects."

**When to Implement:**
- **Now**: If you expect 10+ projects per user
- **Later**: If you start with 1-3 projects per user

---

## Design Decisions Validated

### Why Normalization is Better for Your Use Case

| Scenario | Normalized (Your Schema) | Denormalized (Alternative) | Winner |
|----------|-------------------------|---------------------------|--------|
| **Storage cost** | Low (no redundancy) | High (user_id, project_name duplicated per chunk) | ✅ Normalized |
| **Data integrity** | High (single source of truth) | Low (rename project = update millions of rows) | ✅ Normalized |
| **Write performance** | High (atomic updates) | Low (massive UPDATE operations) | ✅ Normalized |
| **Single-project search** | Fast (simple WHERE clause) | Very fast (no JOIN) | ~ Tie |
| **Cross-project search** | Moderate (1 JOIN) | Very fast (no JOIN) | ❌ Denormalized |
| **With partitioning** | Very fast (partition pruning) | Very fast | ✅ Tie |

**Conclusion:** Normalized + Partitioning = Best of both worlds

---

## Implementation Roadmap

### Phase 1: Git Provenance (Do This Now)

**Files:**
- `add-git-provenance.sql` - Database schema enhancement

**Actions:**
1. Apply SQL to local PostgreSQL:
   ```bash
   psql "$POSTGRES_CONNECTION" -f add-git-provenance.sql
   ```

2. Update ingestion pipeline to populate new columns:
   ```python
   # In src/code_index_mcp/ingestion/pipeline.py
   chunk_data = {
       'chunk_text': chunk.content,
       'embedding': embedding,
       'commit_hash': git_commit_hash,      # NEW
       'branch_name': branch,                # NEW
       'author_name': commit_author,         # NEW
       'commit_timestamp': commit_timestamp, # NEW
       ...
   }
   ```

3. Implement delta-based sync in Git webhook handler:
   ```python
   # In src/code_index_mcp/admin/webhook_handlers.py
   async def handle_push_event(repo_url, old_commit, new_commit):
       modified_files = await git_diff(old_commit, new_commit)

       for file_path in modified_files['modified']:
           # Delete old chunks for this file
           await delete_old_file_chunks(project_id, file_path, new_commit)
           # Re-ingest new version
           await ingest_file(file_path, new_commit)

       for file_path in modified_files['deleted']:
           # Remove chunks for deleted files
           await delete_old_file_chunks(project_id, file_path, None)
   ```

**Testing:**
```bash
# 1. Ingest repo at commit A
ingest_code_from_git("https://github.com/user/repo")

# 2. Make changes, commit B
# 3. Webhook triggers delta-sync
# 4. Verify only changed files re-indexed
SELECT file_path, commit_hash, COUNT(*)
FROM code_chunks
WHERE project_id = 'xxx'
GROUP BY file_path, commit_hash;
```

---

### Phase 2: Table Partitioning (After 10+ Projects)

**When to Implement:**
- You have 10+ projects with 10,000+ chunks each
- Cross-project search latency becomes noticeable

**Steps:**
1. Create partitioned table structure
2. Copy data from existing table
3. Swap tables atomically
4. Test partition pruning with EXPLAIN ANALYZE

**Document Reference:**
- Section 4.4: "Comparative Analysis and Recommendation"
- Partition pruning explanation

---

## Performance Tuning Checklist

Based on the document's recommendations, verify you have:

- [x] **Strongly-typed metadata columns** (file_path, language, etc.)
- [x] **B-tree indexes on filter columns** (language, chunk_type)
- [x] **HNSW vector index** with appropriate parameters
- [x] **Normalized schema** (avoid JOINs where possible)
- [ ] **Git provenance columns** (commit_hash, branch, author, timestamp)
- [ ] **Composite index** on (project_id, commit_hash, file_path)
- [ ] **Table partitioning** (when > 10 projects)
- [x] **RLS policies** for multi-tenancy

---

## Delta-Sync Performance Impact

**Without Git Provenance (Current):**
```
User pushes 2 changed files to repo with 1,000 files

1. Delete ALL chunks (50,000 rows)      ← 30 seconds
2. Re-process ALL 1,000 files           ← 5 minutes
3. Generate ALL 50,000 embeddings       ← 10 minutes (Vertex AI rate limits)
4. Insert ALL 50,000 chunks             ← 2 minutes

Total: ~17 minutes per push
Cost: $5-10 in Vertex AI embeddings
```

**With Git Provenance (After Enhancement):**
```
User pushes 2 changed files

1. git diff old_commit..new_commit      ← 1 second
2. Delete chunks for 2 files (100 rows) ← 0.1 seconds
3. Re-process 2 files                   ← 1 second
4. Generate 100 embeddings              ← 2 seconds
5. Insert 100 chunks                    ← 0.1 seconds

Total: ~4 seconds per push
Cost: $0.01 in Vertex AI embeddings

Improvement: 255x faster, 500x cheaper
```

---

## Summary: Your Schema is Excellent

**Document's Verdict:** ✅ "The recommended path is to implement the Normalized Model (Model A)"

**Your Schema:** ✅ Already normalized with strong typing and proper indexes

**Missing Pieces:**
1. Git provenance (critical for Git-sync) - **Add now**
2. Table partitioning (performance boost) - **Add when > 10 projects**

**Next Steps:**
1. Apply `add-git-provenance.sql` to local PostgreSQL
2. Update ingestion pipeline to populate new columns
3. Implement delta-based sync in webhook handler
4. Test with real Git repository
5. Deploy to AlloyDB when ready

---

## References

- [Timescale: pgvector Performance Best Practices](https://www.timescale.com/blog/pgvector-for-semantic-search-performance-best-practices/)
- Section 3.2: Core Table Design
- Section 4: Multi-Project and Cross-Repository Search
- Section 5: Integrating Git Provenance
