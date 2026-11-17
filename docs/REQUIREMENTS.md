# Requirements: STW Guide

## Functional (what it does)

1. A user can ask a question in plain English and get an answer drawn from my sources.
2. Every answer cites the document and page (or section) it came from.
3. If the documents do not contain the answer, the product says "I don't know" instead of guessing.
4. Signature feature: Decision path view: the answer shows the STW as a highlighted path (symptom, decision, action, refer).
5. A user can browse and search the underlying records through GET /v1/documents.

## Non-functional (how well, with numbers)

| # | Quality | Target | How I will measure it |
|---|---|---|---|
| 1 | Record lookup speed | p95 under 500 ms | load test (Week 6) |
| 2 | Answer speed | p95 under 6 seconds| traces (Week 5) |
| 3 | Accuracy | 90%+ across 40 questions | golden question set (Weeks 4 and 5) |
| 4 | Cost | Under ₹0.50 per question | llm_calls table (Week 2) |
| 5 | Availability | 99% monthly uptime of the live URL | uptime monitor from Day 5 |
