# STW Guide

STW Guide helps PHC doctors access ICMR Standard Treatment Workflows, including red flags, first-line management, and referral criteria, with source citations.

**Status:** Day 3 – PostgreSQL data model, migrations, and data loader. Live URL planned for Day 5.

## Who it's for

An MBBS intern at a Primary Health Centre near Kanchipuram handling approximately 80 outpatient consultations daily.

## The problem

ICMR publishes Standard Treatment Workflows for various medical conditions and specialties. Finding the correct workflow during busy outpatient consultations can be time-consuming. Important red flags and referral criteria must be identified quickly and accurately. Since STWs are presented as flowcharts, extracting their content without losing decision sequences is challenging. Doctors need a reliable way to access structured clinical guidance with accurate references.

## Data sources

ICMR Standard Treatment Workflows across specialties and volumes, including pocket versions.

- [ICMR Standard Treatment Workflows](https://www.icmr.gov.in/standard-treatment-workflows-stws)
- Terms: Public government clinical guidance. Cite the STW title and page.

## Hardest problem (my interview story)

STWs contain flowcharts with boxes, arrows, and clinical decision branches. Plain PDF extraction can scramble their order and lose conditional logic. The parser must preserve layout using coordinates or vision models so that decision branches remain intact and answers cite their original source boxes.

## Signature feature

**Decision Path View:** Highlights the clinical workflow from symptom identification to decision, action, and referral.

## Target metric

Achieve 90%+ referral criteria accuracy across 40 clinician-style questions, evaluated against the original STWs.

## Technology Stack

Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, asyncpg, and Git.

## Run it locally

```bash
uv sync
```

Configure environment variables:

```cmd
copy .env.example .env
```

Run migrations and load data:

```bash
uv run alembic upgrade head
uv run python scripts/load_db.py
```

Start the application:

```bash
uv run uvicorn stw_guide.api.main:create_app --factory --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs).

## Checks

```bash
uv run pytest
uv run ruff check .
```

## Future Enhancements

- Flowchart-aware PDF extraction.
- AI-powered clinical workflow retrieval.
- Source-grounded answers.
- Clinical decision path visualization.
- Clinician-based accuracy evaluation.

---

**STW Guide — Making clinical workflow information accessible and reliable.**
