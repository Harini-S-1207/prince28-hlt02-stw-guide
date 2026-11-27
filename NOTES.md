D01 â€“ Project Foundation and FastAPI Skeleton
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
## D03 â€“ PostgreSQL Implementation Notes
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
Task: D03 â€“ PostgreSQL Implementation
Database: Neon PostgreSQL
Status: Implementation and verification evidence documented.
D04 Â· Docker, Compose and Tests
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
Task: D04 â€“ Docker, Compose and Tests
Status: Implementation and verification completed; 100% statement and branch coverage achieved.

## D05 Â· CI/CD and Going Live

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

### Day 06 â€“ Section 3: Kill it and Resume

**Resume and recovery test results**

| Test | Downloaded | Skipped | Result |
|---|---:|---:|---|
| Interrupted run | 1 | â€” | Passed â€“ stopped safely |
| Resume run | 9 | 1 | Passed |
| Third run | 0 | 10 | Passed â€“ no duplicate downloads |
| Deleted-file recovery | 1 | 9 | Passed â€“ missing file restored |

**Additional verification:**
- No `.part` files remained after the interrupted download.
- Completed files were preserved.
- The manifest recorded completed downloads.
- Missing files were downloaded again automatically.

**Conclusion:** The downloader supports safe interruption, resuming, duplicate prevention, and recovery of missing files.

### Day 06 â€“ Section 4: Reach Your Start Target

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

## D06 Â· Collecting the corpus

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
- Full corpus: **0.19 M tokens, 551 chunks, embedding about â‚¹3, vectors 2 MB**.
- The number that surprised me most, and why: The estimated one-time embedding cost is only about â‚¹3 for 125 PDFs. This makes the initial embedding cost very small.

### One thing that went wrong today, and how I fixed it

- 16 encrypted PDFs initially failed measurement because the AES decryption dependency `cryptography` was missing.
- I added `cryptography` to the project dependencies and updated the report script to decrypt PDFs using an empty password before measuring.
- I cleared the old measurement cache and reran the report. All 50 PDFs were measured successfully, with 0 unreadable files.

## Day 06 â€“ Milestone 3: Parse 20 Files and Read Them

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

### Milestone 4 â€” Full Corpus Parsing and Validation

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

## Milestone 5 â€” Parser comparison


<!-- parsers:start -->
| File | Parsers (A / B) | Pages | A found | B found | Time (A / B) | Better, why |
|---|---|---|---|---|---|---|
| 1771492063-bradyarrthymia13-2-2-24935cb6.pdf | PyMuPDF / pypdf | 1 | 6,174 chars, 15 headings, 2 tables | 4,882 chars, 0 headings, 0 tables | 2.63 s / 0.63 s | PyMuPDF â€” preserves headings and detects tables, but multi-column table structure is partially distorted. |
| 1784807344-chronickidneydisease-updated-4c04a1f3 | PyMuPDF / pypdf | 1 | 12,291 chars, 25 headings, 1 table | 8,070 chars, 0 headings, 0 tables | 1.53 s / 0.69 s | PyMuPDF â€” extracts more text and detects 25 headings. |
| 1784807239-acutekidneyinjury-updated-0aa43119.pdf | PyMuPDF / pypdf | 1 | 6,347 chars, 17 headings, 2 tables | 6,026 chars, 0 headings, 0 tables | 1.24 s / 0.73 s | PyMuPDF â€” detects 17 headings and 2 tables. |
| 1725952330-psychiatry-somatoform-disorder-2dbbac | PyMuPDF / pypdf | 1 | 7,001 chars, 28 headings, 1 table | 6,971 chars, 0 headings, 0 tables | 2.94 s / 1.70 s | PyMuPDF â€” detects 28 headings and preserves more structure. |
| 1725952333-psychiatry-developmental-problems-ff4 | PyMuPDF / pypdf | 1 | 12,396 chars, 13 headings, 3 tables | 7,960 chars, 0 headings, 0 tables | 3.72 s / 1.56 s | PyMuPDF â€” detects 13 headings and 3 tables; some columns are duplicated. |
| 1725952331-psychiatry-psychosis-c4672b3a.pdf | PyMuPDF / pypdf | 1 | 11,651 chars, 10 headings, 5 tables | 7,236 chars, 0 headings, 0 tables | 3.69 s / 0.66 s | PyMuPDF â€” detects 10 headings and 5 tables; flowchart relationships are lost. |
| 1725952335-psychiatry-alcohol-use-disorders-f345 | PyMuPDF / pypdf | 1 | 8,278 chars, 36 headings, 7 tables | 6,446 chars, 0 headings, 0 tables | 3.63 s / 1.79 s | PyMuPDF â€” detects 36 headings and 7 tables. |
| 1725952351-ent-chronic-rhinosinusitis-dd1efa5a.pdf | PyMuPDF / pypdf | 1 | 8,402 chars, 15 headings, 3 tables | 4,972 chars, 0 headings, 0 tables | 1.81 s / 0.87 s | PyMuPDF â€” detects 15 headings and 3 tables. |
| 1725952333-psychiatry-anxiety-disorder-02e44e08 | PyMuPDF / pypdf | 1 | 5,318 chars, 6 headings, 2 tables | 6,002 chars, 0 headings, 0 tables | 3.10 s / 0.86 s | Inconclusive â€” pypdf extracts more characters, but character count alone cannot establish accuracy. |
| 1725952351-ent-epistaxis-38326ddc.pdf | PyMuPDF / pypdf | 1 | 4,282 chars, 39 headings, 0 tables | 4,089 chars, 0 headings, 0 tables | 1.55 s / 0.66 s | PyMuPDF â€” detects 39 headings and extracts more text. |
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


### D07 Â· Parsing my corpus

- Files in the manifest: 51 records (50 unique downloaded files)
- Parsed: 50
- Failed: 0
- Pages in Postgres: 51
- Parsing coverage: 100% of unique downloaded files

### Failures by reason

| Reason | Files | What I did |
|---|---:|---|
| No parsing failures recorded | 0 | All 50 unique downloaded files parsed successfully |

- The one I fixed: N/A â€” no parsing failures were recorded.

### What I saw when I read my parsed pages

- A page where the heading path is right (document, page, path):
  Childhood Emotional Disorders, page 2 â€” stored headings: CHILDHOOD EMOTIONAL DISORDERS â†’ KEEP A HIGH THRESHOLD FOR INVASIVE PROCEDURES â†’ October/2019.
- Something that came out wrong (document, page, what):
  Chronic Rhinosinusitis, page 1 â€” some multi-column content was duplicated or misplaced during extraction.
- A table: Markdown grid or loose text? (document, page):
  Atrial Fibrillation, page 1 â€” Markdown pipe-separated table, but column alignment and repeated content were distorted.

### My parser choice

- For PDFs I use PyMuPDF because it detected headings and tables in the comparison, while pypdf reported zero headings and tables. For example, Bradyarrhythmias: PyMuPDF detected 15 headings and 2 tables, compared with pypdf's 0 headings and 0 tables.
- A kind of document in my corpus that neither parser handles well: Complex multi-column clinical PDFs containing tables and flowcharts.

### One thing that went wrong today, and how I fixed it

My SQL query initially referenced p.metadata, but the metadata column belongs to the documents table. I corrected the query to use d.metadata.


### Corpus Quality Evaluation

**Objective:** Evaluate the quality of extracted pages after parsing, rather than relying only on successful parsing status.

#### Implementation

- Created `src/stw_guide/ingest/quality.py` with a reusable document quality evaluator.
- Added checks for empty pages, short pages and explicit headings.
- Distinguished explicit headings found in page text from inherited heading context.
- Integrated quality reports into the existing `documents.metadata` JSONB field in `store.py`.
- Created `scripts/audit_corpus_quality.py` to audit documents already stored in PostgreSQL without downloading or re-parsing PDFs.
- Preserved existing document metadata and table counts during the audit.

| Metric | Result |
|---|---:|
| Documents audited | 50 |
| Passed | 50 |
| Needs review | 0 |
| Total pages | 51 |
| Empty pages | 0 |
| Short pages | 0 |
| Verified boilerplate pages | 1 |
| Total extracted characters | 384,786 |
| Explicit headings detected | 1,290 |
| Heading coverage | 100.00% |

#### Verified Boilerplate Page

| Document | Page | Characters | Observation |
|---|---:|---:|---|
| CLINICAL | 2 | 17 | Contains only `stw.icmr.org.in`, a verified website marker |

- The original PDF page was inspected and confirmed to contain the same website marker.
- The extracted text was preserved; it was not deleted or modified.
- This known marker is classified as boilerplate rather than a short-content warning.
- The 50-character threshold remains unchanged.
- Other unrecognized short pages continue to trigger review warnings.

#### Quality Evaluation Decisions

- A successfully parsed document is not automatically considered high quality.
- Empty and short pages are flagged for review.
- Heading coverage measures the percentage of stored pages containing at least one explicitly detected heading. It does not establish semantic heading accuracy.
- Complex multi-column tables and flowcharts still require visual inspection against their source PDFs.
- Quality warnings are kept separate from the parser failure records.

#### Validation

- Quality evaluator unit tests: 10 passed.
- Combined quality and parser unit tests: 39 passed.
- Storage integration tests: 4 passed.
- Full project test suite: 126 passed, 0 failed.
- Ruff lint check: passed.
- Ruff formatting check: 59 files already formatted.
- Git whitespace check (`git diff --check`): passed.
- Corpus audit: 50 documents evaluated successfully.

**Outcome:** Added measurable extraction-quality evaluation to the STW Guide ingestion pipeline without introducing a database migration or re-parsing the existing corpus.
**Quality result:** All 50 documents passed the defined automated checks. One verified boilerplate page was identified and preserved. This result does not establish semantic accuracy of all extracted tables, diagrams, or clinical content.

### Day 07 â€“ Production Deployment Verification

**Deployment status:** Successful

- Pull request for `feat/day-07-parse` was merged into `main`.
- GitHub Actions deployment workflow completed successfully.
- Neon database migration step passed.
- Exact Docker image deployment to Render succeeded.
- Production smoke test passed.

**Live verification**

| Check | Result |
|---|---|
| `/health` | `status: ok` |
| Application | `stw_guide` |
| Environment | `production` |
| `/ready` | `status: ready` |
| Database readiness | `true` |

**Deployed version:**
`ede88ec6243e98ada3dbeb7d53f037742e51b195`

**Outcome:** The Day 07 corpus parsing and quality evaluation changes are merged into `main`, deployed to production, and verified using the live health and readiness endpoints.


### D08 â€“ Provider connectivity

- Gemini: HTTP 503 (UNAVAILABLE).
  Reason: Model experiencing high demand.
- Groq: Successful connection.
  Model: openai/gpt-oss-20b
  Response: pong
  Latency: 522 ms
  Input tokens: 77
  Output tokens: 45

- No API keys exposed.
- Gemini issue appears provider-side; retry later.

### D08 â€“ LLM Gateway, Fallback and Usage Tracking

**Objective:** Give STW Guide an AI response capability with provider fallback, streaming support, and usage tracking.

**Implementation completed:**
- Added `LLMGateway` with Gemini as the primary provider and Groq as the fallback.
- Added OpenAI-compatible provider integration.
- Implemented retry handling with backoff for retryable errors.
- Added circuit breaker support.
- Implemented streaming with no provider switching after the first response piece.
- Added token estimation, latency measurement, and INR cost estimation.
- Added PostgreSQL `llm_calls` table and migration.
- Added usage recording and daily usage aggregation.
- Added chat and usage API routes.
- Added a system prompt with safeguards against fabricated ICMR references and medical guidance.

**Testing results:**
- Full project test suite passed.
- Total statements: 1,196.
- Missed statements: 0.
- Total branches: 258.
- Partial branches: 0.
- Statement coverage: 100%.
- Branch coverage: 100%.
- 28 files skipped from the coverage table because they have complete coverage.
- Two non-fatal dependency warnings were reported.

**Provider connectivity check (historical):**
- Gemini returned HTTP 503 (UNAVAILABLE) during the recorded check.
- Groq successfully returned `pong`.
- Groq model: `openai/gpt-oss-20b`.
- Recorded latency: 522 ms.
- Gemini connectivity requires another verification.

**Outcome:** Day 08 implementation and automated coverage checks completed successfully. Live provider verification was performed during Milestone 5. Gemini returned HTTP 503, while Groq fallback succeeded. Documentation review and Git submission checks are recorded below.

## Milestone 5 â€” Break it on purpose

### 1. English vs Tamil token experiment

| Test | Input tokens |
|---|---:|
| Hi | 337 |
| English refund question | 345 |
| Tamil refund question | 359 |

- English message tokens: 345 âˆ’ 337 = 8
- Tamil message tokens: 359 âˆ’ 337 = 22
- Tamil/English ratio: 22 Ã· 8 = 2.75Ã—

Observations:
- English response: "I am not sure."
- Tamil response was empty despite reaching 2,048 output tokens.
- Both requests used Groq fallback.

### 2. Questions the system cannot answer

**Question:** Is the district hospital ICU bed free tonight?

Response: "I'm sorry, but I can't help with that."

Observation: The system did not invent real-time hospital bed availability.

**Off-topic question:** Who won the 2011 cricket world cup?

Response: "I am not sure."

Observation: The system did not answer, but did not explicitly identify the question as outside the STW Guide subject.

**Additional observation:** The acute diarrhoea red-flags response contained unverified clinical details and exceeded the prompt's 120-word limit. Documents were not connected, so the answer must not be treated as verified ICMR guidance.

### 3. Primary failure, fallback and circuit breaker

Temporarily configured:

`LLM_PRIMARY_MODEL=gemini-no-such-model`

Results:
- Four consecutive requests received responses from Groq.
- All four Gemini attempts returned HTTP 404.
- Groq successfully handled all four requests.
- Gemini was still called on the fourth request.
- After waiting more than 30 seconds, Gemini was called again and returned HTTP 404.

Conclusion:
- Primary-provider failure: verified.
- Groq fallback: verified.
- Circuit opening after three failures: not observed.
- Half-open retry: attempted, but Gemini still failed.

Restored the original model configuration: `gemini-3.8-flash`.

Restoration test:
- Gemini returned HTTP 503.
- Groq fallback succeeded.
- `fallback_used=true`.

### 4. Usage and cost verification

`GET /v1/usage` returned:

| Metric | Value |
|---|---:|
| Calls | 29 |
| Errors | 14 |
| Fallbacks | 15 |
| Input tokens | 5,250 |
| Output tokens | 5,597 |
| Estimated cost | â‚¹0.1969 |

Neon SQL verification:
- Failed Gemini requests were recorded with status `error`.
- Failed calls had zero input tokens, zero output tokens and zero cost.
- Groq fallback requests were recorded successfully.
- Successful Groq fallback rows had `fallback_used=true`.

Conclusion: Usage tracking and provider-attempt logging were verified. â‚¹0.1969 is the estimated list-price cost, not the actual provider invoice.

### Question 1 â€” Acute and persistent diarrhea

**Question:** According to the ICMR STW, how many days define acute diarrhea and persistent diarrhea?

**Correct ICMR reference answer:**
- Acute diarrhea: Less than 14 days.
- Persistent diarrhea: More than 14 days.

**Actual AI response:**
- Acute diarrhea: Less than 14 days.
- Persistent diarrhea: More than 14 days.

**Finding:** The AI answer matched the ICMR reference. No incorrect detail was identified in this test.

### Milestone 5 â€” Document-based testing: Question 2

**Question:** According to the ICMR STW, what four signs are used to classify severe dehydration in a child?

**Actual AI response:** Incorrect. It claimed three signs were required and provided signs that did not match the ICMR classification.

**Correct ICMR reference answer:**
1. Lethargy or unconsciousness.
2. Sunken eyes.
3. Unable to drink or drinking poorly.
4. Skin pinch goes back very slowly (more than 2 seconds).

Two or more of these four signs classify severe dehydration.

**Finding:** The model generated incorrect clinical details because it did not retrieve the relevant ICMR document. This demonstrates the need for retrieval-grounded answers.

### D08 Â· LLM gateway

- Primary: `gemini-3.8-flash` (Gemini)
- Fallback: `openai/gpt-oss-20b` (Groq)
- First question on my laptop: first words after **not measured** s, total **not measured** s, tokens in **337** / out **not reliably measured**, cost Rs **not measured**.
- Same question on my live URL (second, awake request): **pending live deployment test**.
- Day 1 target: under 1.5 s.

### Tokens: English against Tamil

| Message | tokens in |
|---|---:|
| "Hi" (baseline: mostly my system prompt) | 337 |
| The English sentence | 345 |
| The same sentence in Tamil | 359 |

- English incremental tokens: 8.
- Tamil incremental tokens: 22.
- The Tamil message needs about **2.75 times** the tokens of the English one.

### What the model does without my documents

- Question 6 ("Is the district hospital ICU bed free tonight?"): It did not invent availability. Exact response: "Iâ€™m sorry, but I canâ€™t help with that."
- A detail it got wrong: Severe dehydration classification â†’ the model claimed three signs were required and included incorrect signs. The ICMR reference requires two or more of four signs: lethargy/unconsciousness, sunken eyes, unable to drink or drinking poorly, and skin pinch returning very slowly (more than 2 seconds).
- The off-topic question ("Who won the 2011 cricket world cup?"): It declined with "I am not sure."

### Fallback and circuit breaker

- With the primary broken: provider **Groq**, fallback **true**. First words timing: not measured.
- The question at which "llm call gemini â€¦ error" stopped appearing in the log: **not observed**. Gemini was still called on the fourth request and after the 30-second wait.
- Half-open retry was attempted, but Gemini returned HTTP 404.
- After restoring the original model, Gemini returned HTTP 503 and Groq fallback succeeded.

### The bill

- `/v1/usage` today: calls **29**, errors **14**, fallbacks **15**, estimated cost **Rs 0.1969**.
- Average per successful answered call: approximately **Rs 0.0131** (estimated list-price cost).
- Day 1 target: under Rs 0.50.
- Note: This is estimated cost, not the actual provider invoice.

### One thing that went wrong today, and how I fixed it

The Docker image initially did not include the `prompts` directory. I added `COPY --chown=app:app prompts ./prompts` to the runtime stage of the Dockerfile. The image built successfully, and the container started after I supplied the required environment variables. The local `/health` endpoint returned HTTP 200.

## D09 - Prompt versions compared

<!-- prompts:start -->

| Prompt version | Correct | Accuracy | Invalid replies | Avg tokens in |
|---|---:|---:|---:|---:|
| classify_v1 | 20/20 | 100% | 0 | 268 |
| classify_v2 | 20/20 | 100% | 0 | 266 |
| classify_v3 | 20/20 | 100% | 0 | 396 |
| classify_v4 | 20/20 | 100% | 0 | 316 |

<!-- prompts:end -->


### Prompt iteration history

- Original classify_v1 baseline: 11/20 (55%), with 3 invalid replies.
- Improved classify_v1: 20/20 (100%).
- classify_v2: 20/20 (100%).
- classify_v3: 20/20 (100%).
- classify_v4: 20/20 (100%).
- Original v1 preserved at eval/archive/classify_v1_original.md.
- Final evaluation: 80/80 correct classifications with zero invalid replies.
- No prompt leaks reported during the final comparison.

## D09 - Metadata extraction source verification

### Five-document trial

- Prompt: `extract_v1`
- Documents successfully extracted: 5
- Repaired responses: 3
- Failed documents: 0
- Input tokens: 21,452
- Output tokens: 8,235
- Reported cost: Rs 0.3875
- Duration: 220 seconds
- Model: `openai/gpt-oss-20b`

### Manual source verification

The initial two original ICMR PDFs are documented in detail below; three additional PDFs were verified and are summarized in the table.

1. Acute paralysis:
   - Source: `data/raw/icmr/1725952346-neurology-acute-paralysis-2b5cb3aa.pdf`
   - Source title: Approach to Acute Paralysis.
   - Publication date: October 2019.
   - Extracted condition and clinical warning signs were supported by the source.
   - Specialty was empty; the inspected pages did not explicitly identify a department.

2. Acute kidney injury:
   - Source: `data/raw/icmr/1784807239-acutekidneyinjury-updated-0aa43119.pdf`
   - Source title: Acute Kidney Injury.
   - Publication date: July 2026.
   - Extracted condition, preliminary actions and referral warning signs were supported by the source.
   - Red flags and referral criteria overlapped because the source groups them under urgent referral.

### Observed limitations

- Some source PDF titles are generic or truncated in document metadata.
- Some model responses required repair because list values exceeded the schema's length or item limits.
- A valid structured response still requires manual source verification for factual accuracy.

### Manual verification of five original ICMR PDFs

Five extracted metadata records were checked against their original PDF documents.

| Document | Verification result | Observation |
|---|---|---|
| Acute Paralysis | Supported | Condition and clinical warning signs matched the source. Specialty was not explicitly identified. |
| Acute Kidney Injury | Supported | Condition, preliminary actions and referral warning signs matched the source. Red flags and referral criteria overlapped in the source. |
| Alcohol Use Disorders | Mostly supported | Condition, topics, summary, warning signs and admission criteria matched. Extracted year was null, although the source states October 2019. |
| Neonatal Sepsis | Supported | Condition, red flags and first-line recommendations matched. Extracted year was null, although the source states July 2020. |
| Neonatal Respiratory Distress | Supported | Condition, topics, oxygen therapy, CPAP, surfactant and referral criteria matched. Extracted year 2020 matched the source. |

#### Findings

- Five original ICMR PDFs were manually inspected.
- Two documents had missing publication years despite dates being present in the source PDFs.
- Specialty classification should be interpreted cautiously when it is not explicitly stated in the document.
- Automated schema validation confirms structure, not complete clinical accuracy.
- Manual verification remains important for checking extracted clinical information against source documents.

## D09 - Live API verification

Production deployment was verified using the Render URL.

| Endpoint / filter | Result | Status |
|---|---|---|
| `/health` | HTTP 200; application status `ok`; environment `production` | Passed |
| `/v1/usage` | HTTP 200; usage records returned for the last 7 days | Passed |
| `/v1/documents?doc_kind=guideline&limit=3` | Returned 3 matching documents | Passed |
| `/v1/documents?language=en&limit=3` | Returned 3 matching documents | Passed |
| `/v1/documents?condition=sepsis%20in%20neonates&limit=3` | Returned 1 matching Neonatal Sepsis document | Passed |

The initial condition query used `neonatal sepsis` and returned zero matches. The exact extracted value, `sepsis in neonates`, returned the expected document. This confirmed that list-value filtering works when the supplied value matches the stored metadata.

The usage endpoint initially experienced a connection reset, but a retry returned HTTP 200.

The production health endpoint reported application status `ok` and environment `production`.

### D09 - Prompts and structured output

- Best router prompt: `classify_v2` — 20/20 correct (100%). It achieved the same accuracy as the other final versions with the lowest average input-token count (266).
- Original `classify_v1` scored 11/20 (55%) with 3 invalid replies. After revision, it scored 20/20 (100%) with no invalid replies.
- `classify_v4` scored 20/20 (100%); average input tokens were 316.
- Average input tokens per question: v1 268; best version (`classify_v2`) 266.
- No incorrect answers remained in the final 20-question evaluation set. This does not guarantee correctness on unseen questions.
- Changes to evaluation labels: not established by the recorded comparison results; no label changes are claimed.
### My contract (DocMeta)

- The implemented fields are `doc_kind`, `year`, `language`, `summary`, `topics`, `condition`, `specialty`, `red_flags`, `first_line`, and `referral_criteria`.
- The contract uses constrained values and length limits to keep extracted metadata consistent.
- Unknown publication years can be null; unavailable list values can be empty.
- The exact fields removed from the original project card are not recorded in the available notes, so no field removals are claimed.

### Extraction run

- Prompt version: `extract_v1`.
- Latest confirmed corpus status: 41 documents successfully extracted, 0 failed, 9 pending, out of 50 target documents.
- Latest one-document run: 1 successful, 0 repaired, 0 failed; 2,490 input tokens, 1,296 output tokens; estimated cost ₹0.0547.
- Full-corpus extraction did not finish because the Gemini provider returned HTTP 429 quota errors. The pipeline stopped safely and can resume.
- Five original ICMR PDFs were manually checked against their source documents. Two extracted records had missing publication years even though dates were present in the PDFs.
- Extraction cost for the complete corpus is not yet final. The five-document trial cost ₹0.3875.
- Five-document trial cost per document: approximately ₹0.0775. This is a trial average, not the final corpus cost.

### One thing that went wrong today, and how I fixed it

The extraction provider quota was exhausted during the full-corpus run. I verified that the pipeline remained resumable, waited before retrying, and successfully extracted one additional document. A later run stopped safely when Gemini returned HTTP 429. No previously successful records were lost.

#### Prompt evolution: v3 to v4

- v3 used six examples to demonstrate the three classification labels.
- v4 removed the examples and replaced them with an explicit decision boundary.
- The key improvement was clarifying that questions about ICMR STW recommendations remain `docs`, even when phrased as patient scenarios.
- v4 also clarified that questions about an individual patient's current measurements, treatment progress or facility availability belong to `personal`.
- Both versions retained the instruction that text inside the question tags is data, not an instruction.
- Both versions achieved 20/20 on the final 20-question evaluation set.
- v4 therefore achieved the same measured accuracy with a more explicit classification boundary, although the test set is too small to establish general performance.

### D09 - Automated test verification

| Test category | Result |
|---|---:|
| Unit tests | 209 passed |
| Integration tests | 16 passed |
| Total | 225 passed |
| Ruff lint | Passed |
| Ruff formatting | Passed (88 files) |

Integration tests were executed against the local PostgreSQL test database using `TEST_DATABASE_URL`. All 16 integration tests passed, including database, metadata extraction storage, LLM call recording and parsing storage tests.

Two dependency warnings were reported during testing; neither caused test failures.

### D09 - Final Metadata Extraction Results (2026-11-27)

#### Corpus completion

| Metric | Result |
|---|---:|
| Target documents | 50 |
| Successfully extracted | 50 |
| Pending | 0 |
| Failed | 0 |

The final database status query reported 50 extracted documents and zero pending documents.

#### Resumed extraction evidence

Five recorded extraction batches completed the remaining work:

| Metric | Result |
|---|---:|
| Successful extractions | 8 |
| Repaired responses | 1 |
| Failed extractions | 0 |
| Input tokens | 24,267 |
| Output tokens | 9,278 |
| Estimated batch cost | Rs. 0.4374 |
| Total duration | 253 seconds |

These cost and token figures cover only the five recorded batches, not the entire 50-document corpus.

#### Final testing

| Verification | Result |
|---|---|
| Unit tests | 209 passed |
| Integration tests | 16 passed |
| Combined passing tests | 225 |
| Ruff lint | Passed |
| Ruff formatting | Passed (88 files) |
| PostgreSQL container | Healthy |
| Redis container | Healthy |

The full test command skipped 16 integration tests; those tests were separately executed and passed using `uv run poe test-integration`.

Two non-blocking dependency warnings appeared during testing.

#### Final outcome

The 50-document extraction target was completed with zero pending and zero failed records reported by the database status query. Unit tests, integration tests, lint and formatting checks passed. The earlier provider quota interruptions and successful resumable extraction process remain documented in the development history.


---

# Day 10 — Asynchronous Document Ingestion

Date: 2026-11-27
Branch: `feat/day-10-queue`

## 1. Objective

Implement asynchronous document ingestion using Redis and ARQ so that long-running document processing happens in background workers instead of blocking API requests.

## 2. Implementation Completed

### Database
- Added `IngestJob` and `IngestItem` models.
- Created Alembic migration `77017a8519c0`.
- Added job and item status tracking, retry attempts, error details and page counts.
- Applied migration successfully.

### Redis Queue
- Added ARQ dependency.
- Implemented `src/stw_guide/workers/queue.py`.
- Added Redis connection settings and queue submission.
- Used deterministic job IDs to prevent duplicate queue submissions.

### Ingestion Worker
- Implemented `src/stw_guide/workers/ingest.py`.
- Added document planning and SHA256-based duplicate detection.
- Added file retrieval, parsing and metadata extraction.
- Implemented retry handling and permanent failure handling.
- Added request pacing to control processing rate.

### Worker Lifecycle
- Implemented `src/stw_guide/workers/main.py`.
- Added worker startup and shutdown handling.
- Added recovery of unfinished jobs from PostgreSQL into Redis.
- Added the `worker` Poe task.

## 3. Testing Results

| Test category | Result |
|---|---:|
| Existing and new unit tests | 229 passed |
| Integration tests | 20 passed |
| Combined test run | 249 passed |
| Failed tests | 0 |

### Ingestion-specific tests
- 20 ingestion unit tests passed.
- 4 PostgreSQL ingestion integration tests passed.

## 4. Quality Checks

| Check | Result |
|---|---|
| Ruff check | Passed |
| Ruff format | 95 files already formatted |
| PostgreSQL health | Passed |
| Redis health | Passed |
| Redis queue connection | Passed |
| ARQ worker configuration | Passed |
| Actual ARQ worker startup | Passed |

Worker startup log confirmed:

`Starting worker for 1 functions: ingest_document`

`Worker ready; 0 unfinished item(s) restored to Redis`

## 5. Issues and Fixes

- Installed and configured ARQ for background job processing.
- Fixed import ordering using Ruff.
- Applied Ruff formatting to the affected files.
- Verified Redis connectivity using `scripts/check_redis.py`.
- Confirmed that the worker starts and performs its recovery check successfully.

## 6. Final Outcome

Implemented the asynchronous ingestion foundation using PostgreSQL, Redis and ARQ. Verified queue connectivity, worker startup, job processing behaviour, retry handling, duplicate protection and database integration.

Final combined test result: **249 passed, 0 failed**.

Code-quality checks and worker startup verification completed successfully.

**Status:** Day 10 implementation and validation completed. Git submission is pending.
