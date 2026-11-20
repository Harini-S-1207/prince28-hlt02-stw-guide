D01 – Project Foundation and FastAPI Skeleton
1. Project Environment
The STW Guide project foundation was established using a structured Python project layout.
- Python project managed with uv
- Dependencies and project configuration maintained in pyproject.toml and uv.lock
- Application code organized under the src/stw_guide/ package
2. FastAPI Application Skeleton
A FastAPI application skeleton was created for the STW Guide service. The foundation included the application structure and core API components needed for further development.

Implemented components included:
- FastAPI application setup
- API routes and dependency wiring
- Application configuration
- Request middleware
- Error handling
- Structured logging
- Health and readiness endpoints
3. Quality Gates and Development Tools
Development quality checks and repository safeguards were configured.
- Ruff for linting and formatting
- Pytest for automated testing
- Pre-commit hooks for checks before commits
- Detect-secrets for secret scanning
- .gitignore for excluding local and generated files
- .env.example for documenting required environment configuration
4. Initial Documentation and Testing
The initial project documentation and automated test foundation were established. The project README was prepared, and tests were added to verify core API behavior and configuration.
5. Day 1 Outcome
The initial STW Guide foundation was established with a structured Python package, FastAPI skeleton, core API components, development quality gates and initial documentation. This provided the base for the PostgreSQL implementation and Docker work completed in later days.
D03 – PostgreSQL Implementation Notes
1. Database Setup
- Database: Neon PostgreSQL
- PostgreSQL version: 18.7
- Python database driver: asyncpg
- ORM: SQLAlchemy 2.x
- Migration tool: Alembic
Database connectivity was verified using:
uv run python scripts/db_check.py
Output:
Connected to database 'neondb'
PostgreSQL 18.7 (a21afb5) on aarch64-unknown-linux-gnu,
compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit
The database URL is loaded from environment settings.
The .env file is excluded from Git.
2. Database Models
Two SQLAlchemy models were implemented.
Document
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
Page
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
3. Database Migrations
Two migrations were created and tested.
Migration	Description
2534330a0922	Create documents and pages
ddf8fcd70abe	Add GIN index on metadata


Migration verification:
uv run alembic current
Output:
ddf8fcd70abe (head)
Upgrade and downgrade operations were tested successfully.
4. Idempotent Data Loader
Script: scripts/load_db.py

Sample dataset: data/sample_records.json

The loader:
- Reads sample STW records from JSON.
- Calculates SHA256 hashes.
- Inserts new documents.
- Updates changed documents.
- Skips unchanged documents.
- Uses external_id to identify existing documents.
Loader execution results
Execution	Inserted	Updated	Unchanged
First run	20	0	0
After adding source_url to all records	0	20	0
Repeat run	0	0	20


Verification:
- First run inserted all 20 records.
- Adding source_url changed the SHA256 fingerprints, so all 20 existing records were updated.
- The repeat run detected all 20 records as unchanged.
- No duplicate records were inserted.
The loader's insert, update and unchanged behaviour was verified successfully.
5. PostgreSQL Query Plan Analysis
Script: scripts/explain.py

The script uses PostgreSQL EXPLAIN ANALYZE and BUFFERS to inspect JSONB filtering performance.
Query
EXPLAIN (ANALYZE, BUFFERS)
SELECT external_id, title
FROM documents
WHERE metadata @> '{"specialty": "Cardiology"}'::jsonb;
Actual EXPLAIN ANALYZE Results
Command:
uv run python scripts/explain.py specialty Cardiology
Normal planner:
Seq Scan on documents
(actual time=2.226..3.659 rows=5.00 loops=1)
Rows Removed by Filter: 15
Execution Time: 3.687 ms
PostgreSQL selected Sequential Scan because the table contains only 20 records, making a full table scan cheaper than using an index.

With sequential scans disabled:
Bitmap Heap Scan on documents
(actual time=3.167..3.196 rows=5.00 loops=1)
  -> Bitmap Index Scan on ix_documents_metadata_gin
     (actual time=3.106..3.106 rows=15.00 loops=1)
Execution Time: 3.237 ms
This confirms that PostgreSQL can use the GIN index for JSONB containment filtering.

Conclusion: The GIN index is available and usable. PostgreSQL's normal planner chooses the execution strategy based on estimated cost, table size, and selectivity.
Query plan observations
- Total documents: 20
- Matching Cardiology documents: 5
- Rows removed by filter: 15
- Execution time: 3.795 ms
- Execution strategy: Sequential Scan
Why PostgreSQL Used Sequential Scan
PostgreSQL selected a Sequential Scan instead of using the GIN index.

The current documents table contains only 20 records.

For a small table, scanning all rows can be cheaper than accessing an index.

The database also considers estimated query costs when selecting an execution plan.
When the GIN Index Is Useful
The index ix_documents_metadata_gin uses PostgreSQL's GIN indexing method with jsonb_path_ops.

It supports JSONB containment queries using the @> operator.

For larger datasets and selective JSONB filters, PostgreSQL may choose the GIN index to reduce the number of rows scanned.

Index usage depends on table size, data distribution, query selectivity and planner cost estimates.
6. PostgreSQL Repository
File: src/stw_guide/repositories/documents.py

Implemented DocumentRepository to read documents from PostgreSQL.

Operations:
- List documents
- Search by title
- Search by external ID
- Retrieve a document by external ID
The repository uses SQLAlchemy asynchronous sessions.
7. API Integration
The API now reads documents from PostgreSQL instead of the old JSON RecordStore.

Implemented endpoints:
Endpoint	Purpose
GET /health	Application health
GET /ready	Database readiness
GET /v1/documents	List documents
GET /v1/documents/{document_id}	Retrieve a document


Additional behaviour:
- Search using the q query parameter
- Limit validation from 1 to 100
- 404 response for missing documents
- 422 response for invalid query parameters
- 503 response when the database is unavailable
The old src/stw_guide/store.py JSON store was removed.
8. API Verification
Endpoints were tested using FastAPI Swagger UI.

Swagger URL:
http://127.0.0.1:8000/docs
Verified:
- Health endpoint returns 200.
- Readiness endpoint returns 200 when PostgreSQL is available.
- Document listing returns database records.
- Individual document retrieval works.
- Search by title works.
- Search by external ID works.
- Invalid limit values return 422.
- Database connection failure returns 503.
9. Testing
Test files:
- tests/conftest.py
- tests/test_api.py
- tests/test_db_integration.py
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
Integration tests are skipped automatically when TEST_DATABASE_URL is not configured.
10. Code Quality
Code quality checks:
uv run ruff check src scripts tests
Formatting verification:
uv run ruff format --check src scripts tests
The checks passed after formatting corrections.
11. Security and Configuration
- Database credentials are stored in .env.
- .env is excluded from Git.
- .env.example provides the configuration template.
- Database URLs are normalized for asyncpg.
- Database sessions are managed through SQLAlchemy.
- Database connections are disposed during application shutdown.
Project: STW Guide
Task: D03 – PostgreSQL Implementation
Database: Neon PostgreSQL
Status: Implementation and verification evidence documented.
D04 · Docker, Compose and Tests
1. Production Docker Image
The project uses a multi-stage Dockerfile.

Implementation details:
- Base image: python:3.12-slim
- Package manager: uv
- Multi-stage build to separate build-time and runtime dependencies.
- Production dependencies only in the final image.
- Application runs using a non-root user.
- .dockerignore excludes unnecessary files from the build context.
Previously built image:
Image: stw-guide:day04
Size: 301 MB
Target: Under 400 MB
The image was successfully built and the non-root user was verified.
Build observations
- Docker uses cached layers when the instructions and their dependencies have not changed.
- Dependency installation layers can be reused when dependency files remain unchanged.
- Changes to application source code require rebuilding the affected layers.
Build time: To be recorded from Docker build output.

Cached build steps: To be recorded from Docker build output.
2. Docker Compose Stack
Docker Compose runs the following services:
Service	Image	Purpose
db	pgvector/pgvector:pg17	PostgreSQL database with pgvector
redis	redis:7-alpine	Redis cache
migrate	Project image	Runs Alembic migrations and loads sample data
api	Project image	Runs the FastAPI application


Port mappings:
- API: 8000:8000
- PostgreSQL: 5433:5432
- Redis: 6379:6379
PostgreSQL data is stored in a persistent Docker volume.
First startup
Command:
docker compose up -d
Migration output:
Running upgrade -> 2534330a0922, create documents and pages
Running upgrade 2534330a0922 -> ddf8fcd70abe, add gin index on metadata

Inserted: 20
Updated: 0
Unchanged: 0
All services started successfully. PostgreSQL and Redis became healthy, migrations completed successfully, and the API became healthy.
Second startup
Commands:
docker compose down
docker compose up -d
Migration output:
Inserted: 0
Updated: 0
Unchanged: 20
No new migrations were required. All 20 existing records were detected as unchanged.

This verifies that PostgreSQL data persists across container recreation and that the data loader is idempotent.
3. Database Failure and Recovery Test
The database failure test was performed by stopping PostgreSQL.

Command:
docker compose stop db
Database stopped
Liveness endpoint:
GET /health

{"status":"ok"}
Readiness endpoint:
GET /ready

{"status":"not_ready","checks":{"database":false}}
Database restarted
Command:
docker compose start db
After PostgreSQL became healthy:
GET /ready

{"status":"ok","checks":{"database":true}}
Why should the load balancer stop traffic instead of restarting the application?
The API process is still alive even when the database is unavailable. The load balancer should stop sending traffic to an instance that is not ready.

Restarting the API will not fix a database outage. Traffic can resume when the database connection recovers and readiness becomes healthy again.
4. Testing and Coverage
Tests are organized into separate unit and integration test directories.
Unit tests
Command:
uv run poe test
Result:
16 passed
Unit tests run without requiring a real PostgreSQL database.
Integration tests
Command:
uv run poe test-integration
Result:
7 passed
Integration tests use a real PostgreSQL database.

A fresh temporary test database is created for the integration test session. Alembic migrations are applied, and the temporary database is dropped after testing.
Combined tests and coverage
Command:
uv run poe cov
Final verified result:
58 passed
0 failed
### Coverage Results

| Metric | Result |
|---|---:|
| Tests passed | 58 |
| Tests failed | 0 |
| Total statements | 266 |
| Missed statements | 0 |
| Branches | 22 |
| Partial branches | 0 |
| Overall coverage | **100%** |

### Coverage Verification

| Coverage Type | Covered | Total | Coverage |
|---|---:|---:|---:|
| Statements | 266 | 266 | 100% |
| Branches | 22 | 22 | 100% |
| Overall | - | - | **100%** |


All measured statements and branches are covered by the test suite. The coverage report skipped 18 files because they already had complete coverage.

One non-blocking Starlette deprecation warning was reported during testing.
5. Code Quality
Command:
uv run poe lint
Result:
All checks passed!
34 files already formatted.
6. Clean Clone Verification
A fresh Git clone was created to verify that the project can be built using committed files.

The following command was executed:
docker compose up --build -d
Results:
- Docker images built successfully.
- PostgreSQL and Redis became healthy.
- Alembic migrations completed successfully.
- API started successfully.
Endpoint verification:
GET /health
{"status":"ok"}
GET /ready
{"status":"ok","checks":{"database":true}}
The clean-clone verification passed.
Project: STW Guide
Task: D04 – Docker, Compose and Tests
Status: Implementation and verification completed; 100% statement and branch coverage achieved.

## D05 · CI/CD and Going Live

### Deployment Details

- **Live URL:** https://stw-guide.onrender.com
- **API documentation:** https://stw-guide.onrender.com/docs
- **Health endpoint:** https://stw-guide.onrender.com/health
- **Readiness endpoint:** https://stw-guide.onrender.com/ready
- **CI/CD platform:** GitHub Actions
- **Hosting platform:** Render
- **Database:** Neon PostgreSQL
- **Container registry:** GitHub Container Registry (GHCR)

### CI/CD Verification

- **CI workflow:** Passed on pull requests.
- **CD workflow:** Automatically triggered after successful CI on main.
- **Deployment strategy:** Deploy the exact SHA-tagged Docker image tested by CI.
- **Database migrations:** Executed before normal deployments.
- **Smoke tests:** Verified `/health`, `/ready`, and `/v1/documents?limit=1`.
- **Latest deployed commit:** `094fcd91b7ad19c961e562a4354dd74939f679d3`
- **Latest successful roll-forward:** CD #6.

### Rollback Drill

- **Rolled back to SHA:** `a025da842684420020aef00657d8e64fbda4dd0e`
- **Rollback workflow:** CD #5
- **Rollback result:** Successful.
- **Neon migrations:** Skipped during rollback.
- **Render deployment:** Successful.
- **Smoke test:** Passed.
- **Rolled forward to SHA:** `094fcd91b7ad19c961e562a4354dd74939f679d3`
- **Roll-forward workflow:** CD #6
- **Roll-forward result:** Successful.

### Rollback and Roll-forward Timing

| Operation | GitHub Actions Run | Total Duration | Deploy Job Duration | Result |
|---|---|---:|---:|---|
| Rollback | CD #5 | 51 seconds | 47 seconds | Successful |
| Roll-forward | CD #6 | 47 seconds | 43 seconds | Successful |

Both operations were manually triggered using the GitHub Actions CD workflow. Exact start and completion clock times were not captured in the screenshots.

**Why is keeping the newer database schema safe during rollback?**

The rollback restores an older application image without reversing database migrations. This is safe when the newer schema remains backward-compatible with the older application version and no destructive schema changes have been introduced.

### Where My Secrets Live

- Neon connection string: GitHub Actions secret `DATABASE_URL` and Render environment variable.
- Render deploy hook: GitHub Actions secret `RENDER_DEPLOY_HOOK`.
- Secrets are not committed to Git or included in the Docker image.

### Monitoring

- **Monitoring service:** UptimeRobot.
- **Monitored endpoint:** https://stw-guide.onrender.com/health
- **Monitoring interval:** 5 minutes.
- **Alert method:** Email.
- **Latest monitor status:** UP.

### Deployment Improvement

One improvement for faster first requests is configuring an appropriate always-on hosting plan or a lightweight warm-up strategy to reduce cold-start delays.

### Week 1 Status

- CI pipeline: Completed.
- CD pipeline: Completed.
- Live deployment: Verified.
- Uptime monitoring: Configured.
- Rollback and roll-forward: Successfully tested.
- README badges and live links: Added.
