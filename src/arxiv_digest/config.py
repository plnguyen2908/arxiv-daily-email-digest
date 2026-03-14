from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - fallback when deps are not installed yet
    def load_dotenv(*_args, **_kwargs):
        return False


@dataclass(frozen=True)
class AppConfig:
    app_env: str
    db_path: Path
    topics_config_path: Path
    data_dir: Path
    text_cache_dir: Path
    email_to: str
    email_from: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_timeout_seconds: int
    smtp_retries: int
    smtp_starttls: bool
    smtp_use_ssl: bool
    smtp_fallback_ssl: bool
    top_k_per_keyword: int
    lookback_hours: int
    max_results_per_topic: int
    request_timeout_seconds: int
    user_agent: str
    output_retention_days: int
    text_cache_retention_days: int
    max_output_files: int
    max_text_cache_files: int
    db_max_runs: int
    db_max_keyword_scores: int
    db_max_sent_log_rows: int
    dry_run_use_last_success: bool
    dry_run_ignore_sent_log: bool
    run_ignore_sent_log: bool
    run_use_last_success: bool
    run_fallback_to_lookback_if_empty: bool
    run_current_date_only: bool
    run_timezone: str


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "on"}


def load_config(project_root: Path) -> AppConfig:
    load_dotenv(project_root / ".env")

    db_path = project_root / _env("DB_PATH", "data/arxiv_digest.db")
    topics_config_path = project_root / _env("TOPICS_CONFIG_PATH", "config/topics.yaml")
    data_dir = project_root / _env("DATA_DIR", "data")
    text_cache_dir = project_root / _env("TEXT_CACHE_DIR", "data/text_cache")

    return AppConfig(
        app_env=_env("APP_ENV", "dev"),
        db_path=db_path,
        topics_config_path=topics_config_path,
        data_dir=data_dir,
        text_cache_dir=text_cache_dir,
        email_to=_env("EMAIL_TO", ""),
        email_from=_env("EMAIL_FROM", ""),
        smtp_host=_env("SMTP_HOST", ""),
        smtp_port=int(_env("SMTP_PORT", "587")),
        smtp_username=_env("SMTP_USERNAME", ""),
        smtp_password=_env("SMTP_PASSWORD", ""),
        smtp_timeout_seconds=int(_env("SMTP_TIMEOUT_SECONDS", "45")),
        smtp_retries=int(_env("SMTP_RETRIES", "2")),
        smtp_starttls=_env_bool("SMTP_STARTTLS", True),
        smtp_use_ssl=_env_bool("SMTP_USE_SSL", False),
        smtp_fallback_ssl=_env_bool("SMTP_FALLBACK_SSL", True),
        top_k_per_keyword=int(_env("TOP_K_PER_KEYWORD", "5")),
        lookback_hours=int(_env("LOOKBACK_HOURS", "72")),
        max_results_per_topic=int(_env("MAX_RESULTS_PER_TOPIC", "120")),
        request_timeout_seconds=int(_env("REQUEST_TIMEOUT_SECONDS", "20")),
        user_agent=_env("ARXIV_USER_AGENT", "arxiv-digest-bot/0.1 (+https://github.com/)"),
        output_retention_days=int(_env("OUTPUT_RETENTION_DAYS", "30")),
        text_cache_retention_days=int(_env("TEXT_CACHE_RETENTION_DAYS", "45")),
        max_output_files=int(_env("MAX_OUTPUT_FILES", "120")),
        max_text_cache_files=int(_env("MAX_TEXT_CACHE_FILES", "2000")),
        db_max_runs=int(_env("DB_MAX_RUNS", "1000")),
        db_max_keyword_scores=int(_env("DB_MAX_KEYWORD_SCORES", "50000")),
        db_max_sent_log_rows=int(_env("DB_MAX_SENT_LOG_ROWS", "100000")),
        dry_run_use_last_success=_env_bool("DRY_RUN_USE_LAST_SUCCESS", False),
        dry_run_ignore_sent_log=_env_bool("DRY_RUN_IGNORE_SENT_LOG", True),
        run_ignore_sent_log=_env_bool("RUN_IGNORE_SENT_LOG", False),
        run_use_last_success=_env_bool("RUN_USE_LAST_SUCCESS", True),
        run_fallback_to_lookback_if_empty=_env_bool("RUN_FALLBACK_TO_LOOKBACK_IF_EMPTY", True),
        run_current_date_only=_env_bool("RUN_CURRENT_DATE_ONLY", True),
        run_timezone=_env("RUN_TIMEZONE", "America/Chicago"),
    )
