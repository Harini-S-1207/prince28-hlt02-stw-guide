
# D03 – PostgreSQL Implementation Notes

## 1. Database Setup

- Database: Neon PostgreSQL
- PostgreSQL version: 18.7
- Python database driver: asyncpg
- ORM: SQLAlchemy 2.x
- Migration tool: Alembic

Database connectivity was verified using:

```bash
uv run python scripts/db_check.py
```

Output:

```text
Connected to database 'neondb'
PostgreSQL 18.7 (a21afb5) on aarch64-unknown-linux-gnu,
compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit
```

The database URL is loaded from environment settings.
The `.env` file is excluded from Git.

## 2. Database Models

Two SQLAlchemy models were implemented.

### Document

Stores STW document information:

- external_id
- title
- source_url
- licence
- doc_type
- published_on
- sha256
- metadata (JSONB)
- created_at
- updated_at

### Page

Stores individual document pages:

- document_id
- page_no
- text

Database constraints and indexes:

- Unique external document ID
- Foreign key from pages to documents
- Cascade delete
- Unique document and page number combination
- Positive page number check constraint
- Document type index
- GIN index on JSONB metadata

## 3. Database Migrations

Two migrations were created and tested.

| Migration | Description |
|---|---|
| `2534330a0922` | Create documents and pages |
| `ddf8fcd70abe` | Add GIN index on metadata |

Migration verification:

```bash
uv run alembic current
```

Output:

```text
ddf8fcd70abe (head)
```

Upgrade and downgrade operations were tested successfully.

## 4. Idempotent Data Loader

Script: `scripts/load_db.py`

Sample dataset: `data/sample_records.json`

The loader:

- Reads sample STW records from JSON.
- Calculates SHA256 hashes.
- Inserts new documents.
- Updates changed documents.
- Skips unchanged documents.
- Uses external_id to identify existing documents.


### Loader execution results

| Execution | Inserted | Updated | Unchanged |
|---|---:|---:|---:|
| First run | 20 | 0 | 0 |
| After adding source_url to all records | 0 | 20 | 0 |
| Repeat run | 0 | 0 | 20 |

**Verification:**
- First run inserted all 20 records.
- Adding `source_url` changed the SHA256 fingerprints, so all 20 existing records were updated.
- The repeat run detected all 20 records as unchanged.
- No duplicate records were inserted.

The loader's insert, update and unchanged behaviour was verified successfully.

## 5. PostgreSQL Query Plan Analysis

Script: `scripts/explain.py`

The script uses PostgreSQL EXPLAIN ANALYZE and BUFFERS to inspect JSONB filtering performance.

### Query

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT external_id, title
FROM documents
WHERE metadata @> '{"specialty": "Cardiology"}'::jsonb;
```


### Actual EXPLAIN ANALYZE Results

Command:
```bash
uv run python scripts/explain.py specialty Cardiology
```

**Normal planner:**
```text
Seq Scan on documents
(actual time=2.226..3.659 rows=5.00 loops=1)
Rows Removed by Filter: 15
Execution Time: 3.687 ms
```

PostgreSQL selected Sequential Scan because the table contains only 20 records, making a full table scan cheaper than using an index.

**With sequential scans disabled:**
```text
Bitmap Heap Scan on documents
(actual time=3.167..3.196 rows=5.00 loops=1)
  -> Bitmap Index Scan on ix_documents_metadata_gin
     (actual time=3.106..3.106 rows=15.00 loops=1)
Execution Time: 3.237 ms
```

This confirms that PostgreSQL can use the GIN index for JSONB containment filtering.

**Conclusion:** The GIN index is available and usable. PostgreSQL's normal planner chooses the execution strategy based on estimated cost, table size, and selectivity.


### Query plan observations

- Total documents: 20
- Matching Cardiology documents: 5
- Rows removed by filter: 15
- Execution time: 3.795 ms
- Execution strategy: Sequential Scan

### Why PostgreSQL Used Sequential Scan

PostgreSQL selected a Sequential Scan instead of using the GIN index.

The current documents table contains only 20 records.

For a small table, scanning all rows can be cheaper than accessing an index.

The database also considers estimated query costs when selecting an execution plan.

### When the GIN Index Is Useful

The index `ix_documents_metadata_gin` uses PostgreSQL's GIN indexing method with `jsonb_path_ops`.

It supports JSONB containment queries using the `@>` operator.

For larger datasets and selective JSONB filters, PostgreSQL may choose the GIN index to reduce the number of rows scanned.

Index usage depends on table size, data distribution, query selectivity and planner cost estimates.

## 6. PostgreSQL Repository

File: `src/stw_guide/repositories/documents.py`

Implemented `DocumentRepository` to read documents from PostgreSQL.

Operations:

- List documents
- Search by title
- Search by external ID
- Retrieve a document by external ID

The repository uses SQLAlchemy asynchronous sessions.

## 7. API Integration

The API now reads documents from PostgreSQL instead of the old JSON RecordStore.

Implemented endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Application health |
| `GET /ready` | Database readiness |
| `GET /v1/documents` | List documents |
| `GET /v1/documents/{document_id}` | Retrieve a document |

Additional behaviour:

- Search using the `q` query parameter
- Limit validation from 1 to 100
- 404 response for missing documents
- 422 response for invalid query parameters
- 503 response when the database is unavailable

The old `src/stw_guide/store.py` JSON store was removed.

## 8. API Verification

Endpoints were tested using FastAPI Swagger UI.

Swagger URL:

```text
http://127.0.0.1:8000/docs
```

Verified:

- Health endpoint returns 200.
- Readiness endpoint returns 200 when PostgreSQL is available.
- Document listing returns database records.
- Individual document retrieval works.
- Search by title works.
- Search by external ID works.
- Invalid limit values return 422.
- Database connection failure returns 503.

## 9. Testing

Test files:

- `tests/conftest.py`
- `tests/test_api.py`
- `tests/test_db_integration.py`

Unit tests cover:

- Health endpoint
- Database readiness
- Database failure handling
- Document listing and pagination
- Search filtering
- Document retrieval
- Missing document handling
- Invalid query parameters
- Request ID handling
- Application settings validation

Three PostgreSQL integration tests were added:

- Database connection verification
- Listing documents from PostgreSQL
- Retrieving a document from PostgreSQL

Integration tests are skipped automatically when `TEST_DATABASE_URL` is not configured.

## 10. Code Quality

Code quality checks:

```bash
uv run ruff check src scripts tests
```

Formatting verification:

```bash
uv run ruff format --check src scripts tests
```

The checks passed after formatting corrections.

## 11. Security and Configuration

- Database credentials are stored in `.env`.
- `.env` is excluded from Git.
- `.env.example` provides the configuration template.
- Database URLs are normalized for asyncpg.
- Database sessions are managed through SQLAlchemy.
- Database connections are disposed during application shutdown.

---

**Project:** STW Guide
**Task:** D03 – PostgreSQL Implementation
**Database:** Neon PostgreSQL
**Status:** Implementation and verification evidence documented.
