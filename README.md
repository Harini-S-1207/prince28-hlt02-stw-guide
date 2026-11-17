# STW Guide

Gives a PHC doctor the ICMR Standard Treatment Workflow for a condition: red flags, first-line management and when to refer, with the STW cited.

**Status:** Day 1 foundation (FastAPI skeleton, quality gates). Live URL from Day 5.

## Who it's for

MBBS intern posted at a Primary Health Centre near Kanchipuram who sees about 80 OPD patients a day.

## The problem

Doctors working in Primary Health Centres often handle many patients in a limited amount of time. Although ICMR provides Standard Treatment Workflows for different medical conditions, finding the correct guideline and understanding its decision-making steps can take time. Important information such as warning signs, first-line treatment and referral criteria may be difficult to locate quickly during a busy OPD. STW Guide aims to make this information easier to find through a simple question-answering system with references to the original ICMR documents.

## Data sources

All ICMR Standard Treatment Workflows (every specialty and volume, including pocket versions) from the ICMR STW page.

- [ICMR Standard Treatment Workflows](https://www.icmr.gov.in/standard-treatment-workflows-stws)
- Terms: Public government clinical guidance. Cite the STW title and page.

## Hardest problem (my interview story)

STWs are flowcharts: boxes and arrows on one page. Plain PDF text extraction scrambles the order and loses the 'if X then Y' logic. The parser must keep layout (coordinates or a vision model) so decision branches stay intact and each answer cites the box it came from.

## Signature feature

Decision path view: the answer shows the STW as a highlighted path (symptom, decision, action, refer).

## Target metric

Referral criteria correct for 90%+ of 40 clinician-style questions, graded against the STW.


## Run it locally

```bash
uv sync
cp .env.example .env
# Windows: copy .env.example .env
uv run uvicorn stw_guide.api.main:create_app --factory --reload
```

Then open [http://localhost:8000/docs](http://localhost:8000/docs)

## Checks

```bash
uv run pytest
uv run ruff check .
```

**Performance targets:** Initial performance targets are designed for a prototype deployment. They will be improved after collecting real usage and performance measurements.
