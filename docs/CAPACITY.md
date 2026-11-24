
# Capacity plan: STW Guide

Full corpus target: All published STWs (125+ PDFs)

<!-- generated:start -->
## Measured on my start corpus (2026-11-23 12:26 UTC)

| What | Value |
|---|---|
| Files | 50 |
| Size on disk | 39.1 MB |
| Pages (PDF pages + 1 per 3,000 characters of text/HTML) | 51 |
| Characters of text | 306,607 |
| Estimated tokens (characters / 4) | 76,652 |
| Tokens per page | 1,503 |
| PDFs with almost no text (scanned? OCR is Day 7) | 0 |
| Files not measured (zip, xlsx, unreadable) | 0 |

## Estimate for the full corpus (target: 125 files)

| What | How | Value |
|---|---|---|
| Scale factor | target / measured | x 2.5 |
| Tokens | measured tokens x scale | 0.19 M |
| Raw files | measured MB x scale | 98 MB |
| Chunks | tokens / 400 x 1.15 overlap | 551 |
| Embedding cost, one time | tokens x 1.15 x $0.15 per 1M | $0.03 = Rs 3 |
| Vector storage | chunks x 768 numbers x 4 bytes | 2 MB |
| Text in Postgres | characters x scale x 1.2 | 1 MB |

Assumptions: 4 characters per token, 400-token chunks, 768-dimension embeddings at $0.15 per 1M tokens, Rs 95 per US dollar.
<!-- generated:end -->

## What I conclude

1. **Embedding cost:** Embedding is not a major concern for this project. The estimated one-time embedding cost for 125 PDFs is approximately $0.03 (₹3), which is very affordable.

2. **Storage:** Vectors and extracted text together require approximately 3 MB of storage. This is comfortably within the 1 GB Neon free-plan limit, excluding indexes and database overhead. I will verify actual storage usage through the Neon dashboard.

3. **Least certain estimate:** The token estimate is based on an approximation of 4 characters per token. This may not be accurate for all documents. I will measure token counts more precisely using the embedding model's tokenizer.

4. **10× corpus growth:** If the corpus grows from 125 to approximately 1,250 PDFs, the estimated token count increases from 0.19 million to 1.9 million, with approximately 5,510 chunks. Embedding costs and storage requirements are also expected to increase roughly 10 times.
