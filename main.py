from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from arxiv_digest.config import load_config
from arxiv_digest.db import init_db
from arxiv_digest.housekeeping import run_housekeeping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily arXiv digest app")
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["status", "init-db", "run", "dry-run", "cleanup"],
        help="Command to run",
    )
    return parser.parse_args()


def run_status() -> None:
    config = load_config(PROJECT_ROOT)
    payload = {
        "app_env": config.app_env,
        "db_path": str(config.db_path),
        "topics_config_path": str(config.topics_config_path),
        "text_cache_dir": str(config.text_cache_dir),
        "top_k_per_keyword": config.top_k_per_keyword,
        "lookback_hours": config.lookback_hours,
        "max_results_per_topic": config.max_results_per_topic,
        "email_to_set": bool(config.email_to),
        "email_from_set": bool(config.email_from),
        "smtp_host_set": bool(config.smtp_host),
        "smtp_port": config.smtp_port,
        "smtp_timeout_seconds": config.smtp_timeout_seconds,
        "smtp_starttls": config.smtp_starttls,
        "smtp_use_ssl": config.smtp_use_ssl,
        "smtp_fallback_ssl": config.smtp_fallback_ssl,
        "output_retention_days": config.output_retention_days,
        "text_cache_retention_days": config.text_cache_retention_days,
        "max_output_files": config.max_output_files,
        "max_text_cache_files": config.max_text_cache_files,
        "db_max_runs": config.db_max_runs,
        "db_max_keyword_scores": config.db_max_keyword_scores,
        "db_max_sent_log_rows": config.db_max_sent_log_rows,
        "dry_run_use_last_success": config.dry_run_use_last_success,
        "dry_run_ignore_sent_log": config.dry_run_ignore_sent_log,
        "run_ignore_sent_log": config.run_ignore_sent_log,
        "run_use_last_success": config.run_use_last_success,
        "run_fallback_to_lookback_if_empty": config.run_fallback_to_lookback_if_empty,
        "run_current_date_only": config.run_current_date_only,
        "run_timezone": config.run_timezone,
    }
    print(json.dumps(payload, indent=2))


def run_init_db() -> None:
    config = load_config(PROJECT_ROOT)
    init_db(config.db_path)
    print(f"Initialized database at {config.db_path}")


def run_pipeline(*, dry_run: bool) -> None:
    from arxiv_digest.pipeline import run_digest

    config = load_config(PROJECT_ROOT)
    init_db(config.db_path)
    result = run_digest(
        cfg=config,
        dry_run=dry_run,
        output_dir=PROJECT_ROOT / "output",
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "status": result.status,
                "total_candidates": result.total_candidates,
                "total_selected": result.total_selected,
                "output_text_path": str(result.output_text_path) if result.output_text_path else None,
                "output_html_path": str(result.output_html_path) if result.output_html_path else None,
            },
            indent=2,
        )
    )


def run_cleanup() -> None:
    config = load_config(PROJECT_ROOT)
    init_db(config.db_path)
    cleanup = run_housekeeping(cfg=config, output_dir=PROJECT_ROOT / "output")
    print(
        json.dumps(
            {
                "deleted_output_files": cleanup.deleted_output_files,
                "deleted_text_cache_entries": cleanup.deleted_text_cache_entries,
                "deleted_keyword_scores": cleanup.deleted_keyword_scores,
                "deleted_sent_log_rows": cleanup.deleted_sent_log_rows,
                "deleted_runs": cleanup.deleted_runs,
            },
            indent=2,
        )
    )


def main() -> int:
    args = parse_args()
    if args.command == "init-db":
        run_init_db()
        return 0
    if args.command == "run":
        run_pipeline(dry_run=False)
        return 0
    if args.command == "dry-run":
        run_pipeline(dry_run=True)
        return 0
    if args.command == "cleanup":
        run_cleanup()
        return 0

    run_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
