PYTHON ?= python3
WORKFLOW_FILE ?= arxiv_digest.yml
MSG ?= "chore: update arxiv digest config"

.PHONY: install init-db status run rerun-all dry-run cleanup test update-config sync-secrets push deploy run-now api-dev frontend-dev docker-build-backend

install:
	$(PYTHON) -m pip install -r requirements.txt

init-db:
	$(PYTHON) main.py init-db

status:
	$(PYTHON) main.py status

run:
	$(PYTHON) main.py run

rerun-all:
	RUN_CURRENT_DATE_ONLY=0 RUN_USE_LAST_SUCCESS=0 RUN_IGNORE_SENT_LOG=1 LOOKBACK_HOURS=168 $(PYTHON) main.py run

dry-run:
	$(PYTHON) main.py dry-run

cleanup:
	$(PYTHON) main.py cleanup

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

api-dev:
	PYTHONPATH=src uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	$(PYTHON) -m http.server 4173 --directory frontend

docker-build-backend:
	docker build -f backend/Dockerfile -t arxiv-interactive-backend .

update-config:
	@echo "Update .env and config/topics.yaml with new email/keywords."
	@echo "Then run: make sync-secrets && make deploy"

sync-secrets:
	@test -f .env || (echo ".env not found. Copy from .env.example first." && exit 1)
	@set -a; . ./.env; set +a; \
	gh secret set EMAIL_TO --body "$$EMAIL_TO"; \
	gh secret set EMAIL_FROM --body "$${EMAIL_FROM:-$$SMTP_USERNAME}"; \
	gh secret set SMTP_HOST --body "$$SMTP_HOST"; \
	gh secret set SMTP_PORT --body "$$SMTP_PORT"; \
	gh secret set SMTP_USERNAME --body "$$SMTP_USERNAME"; \
	gh secret set SMTP_PASSWORD --body "$$SMTP_PASSWORD"; \
	gh secret set SMTP_TIMEOUT_SECONDS --body "$${SMTP_TIMEOUT_SECONDS:-60}"; \
	gh secret set SMTP_RETRIES --body "$${SMTP_RETRIES:-2}"; \
	gh secret set SMTP_STARTTLS --body "$${SMTP_STARTTLS:-0}"; \
	gh secret set SMTP_USE_SSL --body "$${SMTP_USE_SSL:-1}"; \
	gh secret set SMTP_FALLBACK_SSL --body "$${SMTP_FALLBACK_SSL:-1}"; \
	gh secret set ARXIV_USER_AGENT --body "$${ARXIV_USER_AGENT:-arxiv-digest-bot/0.1}"

push:
	git add .
	git commit -m $(MSG) || true
	git push

deploy: sync-secrets push
	@echo "Deployed config and code. Workflow is manual-only unless you re-add a schedule."

run-now:
	gh workflow run $(WORKFLOW_FILE)
