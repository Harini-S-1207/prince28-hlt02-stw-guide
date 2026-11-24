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
## D03 – PostgreSQL Implementation Notes
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

### Day 06 – Section 3: Kill it and Resume

**Resume and recovery test results**

| Test | Downloaded | Skipped | Result |
|---|---:|---:|---|
| Interrupted run | 1 | — | Passed – stopped safely |
| Resume run | 9 | 1 | Passed |
| Third run | 0 | 10 | Passed – no duplicate downloads |
| Deleted-file recovery | 1 | 9 | Passed – missing file restored |

**Additional verification:**
- No `.part` files remained after the interrupted download.
- Completed files were preserved.
- The manifest recorded completed downloads.
- Missing files were downloaded again automatically.

**Conclusion:** The downloader supports safe interruption, resuming, duplicate prevention, and recovery of missing files.

### Day 06 – Section 4: Reach Your Start Target

**Corpus collection completed**

- Total PDF files downloaded: 50
- Unique source URLs: 50
- Manifest records: 51
- Duplicate download-history records: 1
- Download failures: 0
- Blocked sources: 0

**Five selected specialties**

| Specialty | Individual PDFs |
|---|---:|
| Cardiology | 6 |
| ENT | 7 |
| Dermatology | 13 |
| Neonatology | 10 |
| Psychiatry | 8 |
| **Total** | **44** |

Six additional individual ICMR documents from other specialties were also retained.

**Verification**
- All 50 PDF files exist in `data/raw/icmr/`.
- 50 unique URLs are recorded in the manifest.
- The additional manifest record comes from the deleted-file recovery test.
- The manifest was preserved as an append-only download history.

**Conclusion:** Collected 44 PDFs across the five selected specialties and 50 PDFs overall. The exact number of distinct STWs represented by these documents is still being validated, so achievement of the original target of 40 STWs is not yet confirmed.

## D06 · Collecting the corpus

- Start target: 40 STWs from 5 specialties.
- Collected today: **50 files, 51 pages, 39.1 MB**.
- Doors used: URL list.

### Licence check

| Source | Licence or terms, in my words | May I show full text in answers? |
|---|---|---|
| ICMR | ICMR website copyright policy: reproduce accurately with prominent acknowledgement; exclude third-party copyrighted material. | Only within the stated policy; acknowledge ICMR and exclude third-party copyrighted material. |

### robots.txt

- Site: https://www.icmr.gov.in/robots.txt
- Its robots.txt says:
  - `User-agent: *` and `Allow: /`
  - It also provides the sitemap: `https://www.icmr.gov.in/sitemap.xml`
- Was anything blocked for my bot? **No. 0 URLs were blocked.** The downloader respected robots.txt.

### Kill and resume

- Run 1: I pressed Ctrl+C after 1 file.
- Run 2: downloaded=9 skipped=1.
- Run 3: downloaded=0 skipped=10.

### Capacity

- Tokens per page, measured: **1,503**.
- Full corpus: **0.19 M tokens, 551 chunks, embedding about ₹3, vectors 2 MB**.
- The number that surprised me most, and why: The estimated one-time embedding cost is only about ₹3 for 125 PDFs. This makes the initial embedding cost very small.

### One thing that went wrong today, and how I fixed it

- 16 encrypted PDFs initially failed measurement because the AES decryption dependency `cryptography` was missing.
- I added `cryptography` to the project dependencies and updated the report script to decrypt PDFs using an empty password before measuring.
- I cleared the old measurement cache and reran the report. All 50 PDFs were measured successfully, with 0 unreadable files.

## Day 06 – Milestone 3: Parse 20 Files and Read Them

### Objective
Parse downloaded ICMR PDF documents into structured pages and store the extracted content in PostgreSQL.

### Implementation
- Created `scripts/parse_corpus.py`.
- Read downloaded records from `data/manifest.jsonl`.
- Selected the latest manifest record for each URL.
- Processed only downloaded files that exist locally.
- Used the existing PyMuPDF parser.
- Implemented content-based document identification to avoid duplicate processing.
- Added support for retrying previously failed files.
- Added optional OCR fallback for PDFs without a text layer.
- Stored document metadata and extracted pages in Neon PostgreSQL.
- Recorded parsing failures separately in `parse_failures`.

### Execution

Command:

```cmd
uv run --no-sync python scripts/parse_corpus.py --limit 20
```

### Results

| Metric | Result |
|---|---:|
| Available downloaded files | 50 |
| Files processed | 20 |
| Successfully parsed | 20 |
| Parsing failures | 0 |
| Pages stored | 20 |
| Execution time | 35.29 seconds |

All 20 processed documents were successfully stored in Neon PostgreSQL.

### Validation and Quality Checks

- Verified the 20 original PDF files using PyMuPDF.
- Confirmed that all 20 original PDFs contain exactly one page.
- Compared original PDF page counts with the stored page records.
- Inspected five extracted pages using SQL queries.
- Confirmed that medical workflow titles, ICD-10 codes and section content were extracted.
- Observed table extraction across the documents.
- First-page `headings` arrays were empty because no earlier section path existed; heading text was still present in the extracted content.
- No parsing failures occurred during this run.

### Database Verification

Verified the saved documents and pages using Neon SQL Editor.

Tables inspected:
- `documents`
- `pages`

### Reproducible Commands

```cmd
uv run --no-sync python scripts/parse_corpus.py
uv run --no-sync python scripts/parse_corpus.py --limit 20
uv run --no-sync python scripts/parse_corpus.py --retry-failed
uv run --no-sync python scripts/parse_corpus.py --retry-failed --ocr eng
```

### Observations and Limitations

### Text extraction observations

- Inspected extracted page text from 20 parsed documents in Neon.
- Document titles and English medical content were readable.
- Some table and layout formatting imperfections were observed.
- Checked all 40 extracted pages for Tamil Unicode characters: 0 pages contained Tamil Unicode.
- No Tamil legacy-font corruption was confirmed during this inspection.
- Legacy-font issues remain unverified because the inspected corpus may contain English-only documents.

- The first 20 processed PDFs were single-page documents.
- Text extraction was readable in the five inspected records.
- OCR fallback was implemented but was not needed in this run.
- The remaining downloaded files have not yet been processed.
- Further inspection is required to validate extraction quality across the complete corpus.

### Conclusion

Successfully implemented and tested the corpus parsing pipeline. Parsed 20 downloaded ICMR PDFs, stored 20 pages in Neon PostgreSQL, verified the original PDF page counts and inspected the extracted medical content. The run completed with zero parsing failures in 35.29 seconds.

### Milestone 4 — Full Corpus Parsing and Validation

- Ran the parser across the full corpus of 50 downloaded files.
- First full run: 10 newly parsed, 40 already parsed, 0 failures, and 11 pages stored.
- Second full run: 0 newly parsed, 50 already parsed, 0 failures, and 0 new pages.
- Confirmed idempotency: rerunning the parser did not create duplicate documents or pages.
- Queried `parse_failures`: 0 failures out of 50 files.
- Compared 10 documents against their original PDFs:
  - Expected pages: 11
  - Stored pages: 11
  - Page-count mismatches: 0
- Manually checked the psychosis, depression, and childhood emotional disorders PDFs against their extracted content. All three matched.
- No failed files required correction or retry because the failure table was empty.

## Milestone 5 — Parser comparison


<!-- parsers:start -->
| File | Parsers (A / B) | Pages | A found | B found | Time (A / B) | Better, why |
|---|---|---|---|---|---|---|
| 1771492063-bradyarrthymia13-2-2-24935cb6.pdf | PyMuPDF / pypdf | 1 | 6,174 chars, 15 headings, 2 tables | 4,882 chars, 0 headings, 0 tables | 2.63 s / 0.63 s | PyMuPDF — preserves headings and detects tables, but multi-column table structure is partially distorted. |
| 1784807344-chronickidneydisease-updated-4c04a1f3 | PyMuPDF / pypdf | 1 | 12,291 chars, 25 headings, 1 table | 8,070 chars, 0 headings, 0 tables | 1.53 s / 0.69 s | PyMuPDF — extracts more text and detects 25 headings. |
| 1784807239-acutekidneyinjury-updated-0aa43119.pdf | PyMuPDF / pypdf | 1 | 6,347 chars, 17 headings, 2 tables | 6,026 chars, 0 headings, 0 tables | 1.24 s / 0.73 s | PyMuPDF — detects 17 headings and 2 tables. |
| 1725952330-psychiatry-somatoform-disorder-2dbbac | PyMuPDF / pypdf | 1 | 7,001 chars, 28 headings, 1 table | 6,971 chars, 0 headings, 0 tables | 2.94 s / 1.70 s | PyMuPDF — detects 28 headings and preserves more structure. |
| 1725952333-psychiatry-developmental-problems-ff4 | PyMuPDF / pypdf | 1 | 12,396 chars, 13 headings, 3 tables | 7,960 chars, 0 headings, 0 tables | 3.72 s / 1.56 s | PyMuPDF — detects 13 headings and 3 tables; some columns are duplicated. |
| 1725952331-psychiatry-psychosis-c4672b3a.pdf | PyMuPDF / pypdf | 1 | 11,651 chars, 10 headings, 5 tables | 7,236 chars, 0 headings, 0 tables | 3.69 s / 0.66 s | PyMuPDF — detects 10 headings and 5 tables; flowchart relationships are lost. |
| 1725952335-psychiatry-alcohol-use-disorders-f345 | PyMuPDF / pypdf | 1 | 8,278 chars, 36 headings, 7 tables | 6,446 chars, 0 headings, 0 tables | 3.63 s / 1.79 s | PyMuPDF — detects 36 headings and 7 tables. |
| 1725952351-ent-chronic-rhinosinusitis-dd1efa5a.pdf | PyMuPDF / pypdf | 1 | 8,402 chars, 15 headings, 3 tables | 4,972 chars, 0 headings, 0 tables | 1.81 s / 0.87 s | PyMuPDF — detects 15 headings and 3 tables. |
| 1725952333-psychiatry-anxiety-disorder-02e44e08 | PyMuPDF / pypdf | 1 | 5,318 chars, 6 headings, 2 tables | 6,002 chars, 0 headings, 0 tables | 3.10 s / 0.86 s | Inconclusive — pypdf extracts more characters, but character count alone cannot establish accuracy. |
| 1725952351-ent-epistaxis-38326ddc.pdf | PyMuPDF / pypdf | 1 | 4,282 chars, 39 headings, 0 tables | 4,089 chars, 0 headings, 0 tables | 1.55 s / 0.66 s | PyMuPDF — detects 39 headings and extracts more text. |
<!-- parsers:end -->

### Manual PDF Inspection

Three original ICMR PDFs were compared against their extracted PostgreSQL page text.

| Document | Observations |
|---|---|
| Bradyarrhythmias | Main content preserved; multi-column tables partially distorted; ECG diagrams not represented in text. |
| Children with Developmental Problems | Main clinical sections preserved; duplicated columns and layout fragments observed. |
| Psychosis | Main sections preserved; referral tables and treatment algorithm lose structural relationships. |

### Parser Comparison Conclusion

- PyMuPDF provides better structural information for this PDF corpus through heading and table detection.
- pypdf was faster in all 10 recorded comparisons.
- Complex tables, multi-column layouts and flowcharts remain extraction limitations.
- Higher character count does not necessarily indicate better extraction accuracy.
- PyMuPDF is retained as the primary parser for the current corpus.
