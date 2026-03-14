# arXiv Daily Digest

Interactive arXiv tracker with:
- Backend API (manual fetch by today/date, fallback to yesterday if empty)
- Frontend board (paper cards with checkbox completion and paper hyperlinks)
- Keyword editor in UI (writes to `config/topics.yaml`)
- Disk budget guard (delete oldest cached dates when over limit)

You can host:
- Backend on Google Cloud Run (Docker provided)
- Frontend on GitHub Pages (`frontend/` static files)

## New Interactive App (Recommended)

1. Install dependencies.
   - `make install`
2. Run backend API.
   - `make api-dev`
   - API default: `http://localhost:8000`
3. Run frontend locally.
   - `make frontend-dev`
   - Open `http://localhost:4173`
4. In frontend:
   - Set backend URL
   - Fetch `today` or any selected date
   - Tick papers as finished
   - Edit keywords and save

### Backend API endpoints

- `GET /api/health`
- `GET /api/topics`
- `PUT /api/topics`
- `POST /api/fetch` with body `{ \"date\": \"YYYY-MM-DD\", \"force\": true }`
- `GET /api/digest/{date}`
- `POST /api/digest/{date}/toggle`
- `GET /api/dates`

### Docker (Google Cloud Run)

Build locally:
- `make docker-build-backend`

Run locally from image:
- `docker run --rm -p 8080:8080 --env-file .env arxiv-interactive-backend`

Important env vars:
- `RUN_TIMEZONE=America/Chicago`
- `TOPICS_CONFIG_PATH=config/topics.yaml`
- `UI_DATA_DIR=data/ui_store`
- `UI_MAX_DATA_MB=500`
- `UI_FETCH_FALLBACK_DAYS=1`
- `UI_DISK_MAX_USED_PERCENT=90`
- `UI_DISK_MIN_FREE_MB=2048`
- `CORS_ORIGINS=https://<your-gh-pages-domain>`

## Legacy Email Pipeline

The original CLI/email pipeline is still available below.

## Step-by-Step Setup

1. Configure local environment.
   - `cp .env.example .env`
   - Edit `.env` for email settings.
2. Review topics and categories.
   - Edit `config/topics.yaml`.
   - `categories` supports wildcard patterns like `cs.*`.
   - Use `must_have_phrases` per topic to avoid random matches.
3. Install dependencies.
   - `make install`
4. Initialize database.
   - `make init-db`
5. Validate config.
   - `make status`
6. Run a dry test (no email sent).
   - `make dry-run`
7. Run live send.
   - `make run`

## Runtime Commands

- `python main.py status`: show resolved runtime config.
- `python main.py init-db`: create/update SQLite schema.
- `python main.py dry-run`: fetch, filter by keyword in title/abstract, score, summarize, and render email output files only.
- `python main.py run`: full pipeline including SMTP send and sent-log updates.
- `python main.py cleanup`: prune old output/cache files and cap DB table sizes.
- For "everything for the day":
  - set `TOP_K_PER_KEYWORD=0` (all matches, no top-k cap)
  - set `RUN_CURRENT_DATE_ONLY=1` and `RUN_TIMEZONE=America/Chicago`
  - if a run reports `candidates=0`, rerun once; empty candidate pools are treated as transient API/network issues.
  - in current-date mode, cutoff is local midnight of `RUN_TIMEZONE`.
- To rerun everything again (ignore sent-log and last-run window):
  - `make rerun-all`

Dry-run behavior defaults:
- Uses `LOOKBACK_HOURS` window directly (`DRY_RUN_USE_LAST_SUCCESS=0`) so repeated dry-runs still return candidates.
- Ignores sent-log dedupe (`DRY_RUN_IGNORE_SENT_LOG=1`) so you can repeatedly inspect ranking output.

Run behavior:
- `RUN_USE_LAST_SUCCESS=1` (default): send only papers newer than the last successful live run.
- Set `RUN_USE_LAST_SUCCESS=0` to force live runs to use `LOOKBACK_HOURS` window (useful when you want run output to match dry-run retrieval scope).
- `RUN_FALLBACK_TO_LOOKBACK_IF_EMPTY=1` (default): if live run finds zero candidates with last-success cutoff, automatically retry selection using `LOOKBACK_HOURS`.

## Makefile Commands

- `make install`
- `make init-db`
- `make status`
- `make dry-run`
- `make run`
- `make rerun-all`
- `make test`
- `make cleanup`
- `make sync-secrets`
- `make push`
- `make deploy`
- `make run-now`

## GitHub Actions

- Workflow file: `.github/workflows/arxiv_digest.yml`
- Schedule uses UTC cron aligned to arXiv announcement windows.
- Required repository secrets:
  - `EMAIL_TO`
  - `EMAIL_FROM` (optional; defaults to SMTP username if empty)
  - `SMTP_HOST`
  - `SMTP_PORT`
  - `SMTP_USERNAME`
  - `SMTP_PASSWORD`
  - `ARXIV_USER_AGENT`

## Output

- Dry-run and run output are written to `output/<run_id>.txt` and `output/<run_id>.html`.
- Automatic housekeeping runs after each pipeline run:
  - deletes old output files
  - caps `runs`, `keyword_scores`, and `sent_log` table size

## Project Structure

- `main.py`: CLI entrypoint
- `config/topics.yaml`: keyword/category mapping
- `src/arxiv_digest/arxiv_client.py`: arXiv API fetching + Atom parsing
- `src/arxiv_digest/scoring.py`: title+abstract keyword filtering + scoring
- `src/arxiv_digest/summarizer.py`: extractive summary generation
- `src/arxiv_digest/emailer.py`: email rendering + SMTP sending
- `src/arxiv_digest/repository.py`: SQLite persistence and run/sent logs
- `src/arxiv_digest/schema.sql`: database schema
- `tests/`: unit tests
