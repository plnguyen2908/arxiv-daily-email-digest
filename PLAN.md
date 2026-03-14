# Daily arXiv Per-Keyword Top-5 Email App Plan

## Goal
Build a small app that runs every day, and for each keyword, finds the top 5 arXiv papers and emails them to you.

## 1. Requirements and Scope
- Define your topic list (AI, ML, DL, CV, NLP) with keyword aliases and category mapping.
- Use these default arXiv categories:
  - AI: `cs.AI`
  - ML: `cs.LG`, `stat.ML`
  - DL: `cs.LG`, `cs.NE`
  - CV: `cs.CV`, `eess.IV`
  - NLP: `cs.CL`
- Query rule: include papers when `primary_category` is in mapped categories or when categories are cross-listed in mapped categories.
- Ranking output is per keyword: exactly top 5 papers.
- Define a correlation-based relevance score over:
  - Title text
  - Abstract text
  - Full paper text (PDF extraction)
- Use weighted total score (recommended): `0.20 * title_corr + 0.35 * abstract_corr + 0.45 * full_text_corr + 0.10 * category_bonus`.
- Define send schedule (time + timezone) and recipient email.

## 2. Project Setup
- Use Python 3.11+.
- Core packages:
  - `requests` (arXiv API requests)
  - `python-dotenv` (environment variables)
  - `jinja2` (email templating)
  - Optional: `sentence-transformers` for semantic ranking.
- Add local storage with SQLite (`sqlite3`, built-in).

## 3. Data Ingestion from arXiv
- Query arXiv API daily using category-aware filters (not keyword-only search).
- Recommended keyword-to-category retrieval map:
  - `ai` -> `cs.AI`
  - `ml` -> `cs.LG OR stat.ML`
  - `dl` -> `cs.LG OR cs.NE`
  - `cv` -> `cs.CV OR eess.IV`
  - `nlp` -> `cs.CL`
- If needed, run separate arXiv queries per keyword-group and merge unique papers by arXiv ID.
- Fetch fields: arXiv ID, title, authors, abstract, published date, categories, URL, PDF URL.
- Restrict to new papers since last run (or last 24h for first MVP).
- Handle paging and API failures with retries + backoff.
- Download and extract full text from PDFs for correlation scoring.

## 4. Relevance Ranking
- For each keyword, compute a correlation score against each paper field:
  - `title_corr(keyword, title)`
  - `abstract_corr(keyword, abstract)`
  - `full_text_corr(keyword, full_text)`
- Apply a category prior to favor exact domain matches:
  - `category_bonus = 1.0` if primary category matches keyword map
  - `category_bonus = 0.5` if only cross-listed match
  - `category_bonus = 0.0` otherwise
- Combine field scores into one weighted correlation score:
  - `total_corr = 0.20 * title_corr + 0.35 * abstract_corr + 0.45 * full_text_corr + 0.10 * category_bonus`
- Rank papers by `total_corr` and keep top 5 per keyword.
- Tie-breakers:
  - More recent published date first
  - Then arXiv ID lexical order for deterministic output.

## 5. Deduplication and State
- SQLite tables:
  - `papers` (metadata + extracted text hash)
  - `keyword_scores` (keyword, paper_id, title_corr, abstract_corr, full_text_corr, total_corr)
  - `sent_log` (keyword, paper_id, sent_at)
  - `runs` (status, counts, errors)
- Exclude already emailed papers per keyword unless explicitly configured to repeat.

## 6. Email Composition and Delivery
- Create HTML + plain text email template.
- Group results by keyword.
- Include for each paper:
  - Title (linked)
  - Authors
  - Published date
  - Abstract (full text from arXiv metadata)
  - Short summary of what the paper is doing (2-4 sentences)
  - Correlation breakdown (`title_corr`, `abstract_corr`, `full_text_corr`, `total_corr`)
- Summary generation options:
  - MVP: extractive summary from abstract + intro/body snippets
  - Improved: LLM-generated summary with strict factual grounding in the paper text
- Send via SMTP (Gmail app password) or provider API (SendGrid/Postmark).
- Store secrets in `.env` only.

## 7. Daily Scheduling (Aligned to arXiv)
- arXiv posting cycle (Eastern Time):

| Submission window (ET) | Announced (ET) | Mailed by arXiv |
| --- | --- | --- |
| Monday 14:00 to Tuesday 14:00 | Tuesday 20:00 | Tuesday night / Wednesday morning |
| Tuesday 14:00 to Wednesday 14:00 | Wednesday 20:00 | Wednesday night / Thursday morning |
| Wednesday 14:00 to Thursday 14:00 | Thursday 20:00 | Thursday night / Friday morning |
| Thursday 14:00 to Friday 14:00 | Sunday 20:00 | Sunday night / Monday morning |
| Friday 14:00 to Monday 14:00 | Monday 20:00 | Monday night / Tuesday morning |

- Send your digest shortly after each announcement window (not every calendar day).
- GitHub Actions schedule should run on announcement days:
  - Monday, Tuesday, Wednesday, Thursday, Sunday at around 20:00 ET.
- Because GitHub Actions cron uses UTC and ET shifts with daylight savings, use two UTC schedules to cover both EST and EDT.
  - `15 1 * * 1-5` (01:15 UTC; aligns with EST weeks)
  - `15 0 * * 1-5` (00:15 UTC; aligns with EDT weeks)
- Add one manual trigger (`workflow_dispatch`) for test runs.

## 8. Reliability and Observability
- Structured logs for each run.
- Retry transient failures (API/network/email).
- Non-zero exit code on failed runs.
- Optional failure alert email to yourself.

## 9. Testing Strategy
- Unit tests:
  - Correlation scoring logic for each field
  - Weighted total score and tie-break behavior
  - Dedupe logic
  - Email rendering (includes abstract and summary blocks)
  - Summary generation fallback behavior when full text extraction fails
- Integration test:
  - Mock arXiv + sample PDFs -> per-keyword top 5 -> email body generation with abstract + summary.
- Dry-run mode to preview email without sending.

## 10. Security and Ops
- Never hardcode passwords/API keys.
- Validate email and query inputs.
- Add runbook: setup, `.env`, schedule, troubleshooting.
- Add a `Makefile` for repeatable operations when config changes (email/keywords).
- Required `Makefile` targets:
  - `make update-config` to update keyword/email config source (local file or `.env` template).
  - `make sync-secrets` to push updated values to GitHub Actions Secrets (via `gh secret set ...`).
  - `make push` to commit and push branch updates.
  - `make deploy` to run `sync-secrets` + `push` and keep scheduled GitHub Action ready.
  - `make run-now` to trigger manual workflow run (`gh workflow run ...`) for verification.

## 11. Suggested Initial Milestones
1. Scaffold app + config + SQLite schema.
2. Implement arXiv fetch + parser + PDF text extraction.
3. Implement per-keyword correlation scoring + top 5 selection.
4. Implement abstract + summary generation pipeline.
5. Implement email template + sender.
6. Add GitHub Actions scheduler and run logs.
7. Add `Makefile` targets for config update, secret sync, push, and manual trigger.
8. Add tests and dry-run support.
9. Deploy and tune ranking weights after 1 week of real runs.

## Deliverables
- Runnable daily script (`main.py`) with config via `.env`.
- `PLAN.md` (this file).
- `README.md` setup instructions.
- `Makefile` with config/sync/push/trigger commands.
- Basic tests and sample dry-run output.
- `.github/workflows/arxiv_digest.yml` scheduled workflow.
