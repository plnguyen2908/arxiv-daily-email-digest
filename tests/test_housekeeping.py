from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from arxiv_digest.config import AppConfig
from arxiv_digest.db import init_db
from arxiv_digest.housekeeping import cleanup_output_dir, cleanup_text_cache, run_housekeeping


def _touch_with_mtime(path: Path, dt: datetime) -> None:
    path.write_text("x", encoding="utf-8")
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


class HousekeepingTests(unittest.TestCase):
    def test_output_cleanup_by_age_and_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "output"
            out_dir.mkdir(parents=True)
            now = datetime.now(timezone.utc)

            old_file = out_dir / "old.txt"
            _touch_with_mtime(old_file, now - timedelta(days=50))
            for i in range(5):
                _touch_with_mtime(out_dir / f"new_{i}.txt", now - timedelta(days=i))

            deleted = cleanup_output_dir(out_dir, retention_days=30, max_files=3)
            self.assertGreaterEqual(deleted, 3)
            self.assertFalse(old_file.exists())
            self.assertLessEqual(len(list(out_dir.iterdir())), 3)

    def test_text_cache_cleanup_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            cache.mkdir(parents=True)
            now = datetime.now(timezone.utc)

            for i in range(4):
                stem = f"id{i}"
                _touch_with_mtime(cache / f"{stem}.txt", now - timedelta(days=i))
                _touch_with_mtime(cache / f"{stem}.sha256", now - timedelta(days=i))

            deleted = cleanup_text_cache(cache, retention_days=2, max_entries=2)
            self.assertGreater(deleted, 0)

    def test_run_housekeeping_db_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "db.sqlite3"
            out = root / "output"
            cache = root / "cache"
            out.mkdir()
            cache.mkdir()
            init_db(db_path)

            cfg = AppConfig(
                app_env="test",
                db_path=db_path,
                topics_config_path=root / "topics.yaml",
                data_dir=root,
                text_cache_dir=cache,
                email_to="",
                email_from="",
                smtp_host="",
                smtp_port=465,
                smtp_username="",
                smtp_password="",
                smtp_timeout_seconds=10,
                smtp_retries=1,
                smtp_starttls=False,
                smtp_use_ssl=True,
                smtp_fallback_ssl=True,
                top_k_per_keyword=5,
                lookback_hours=72,
                max_results_per_topic=10,
                request_timeout_seconds=10,
                user_agent="ua",
                output_retention_days=30,
                text_cache_retention_days=30,
                max_output_files=10,
                max_text_cache_files=10,
                db_max_runs=2,
                db_max_keyword_scores=3,
                db_max_sent_log_rows=3,
                dry_run_use_last_success=False,
                dry_run_ignore_sent_log=True,
                run_ignore_sent_log=False,
                run_use_last_success=True,
                run_fallback_to_lookback_if_empty=True,
                run_current_date_only=True,
                run_timezone="America/Chicago",
            )

            import sqlite3

            with sqlite3.connect(db_path) as conn:
                for i in range(6):
                    conn.execute(
                        "INSERT INTO runs(run_id, started_at, status, notes) VALUES (?, ?, 'success', '')",
                        (f"r{i}", f"2026-03-01T00:00:0{i}+00:00"),
                    )
                conn.commit()

            result = run_housekeeping(cfg, out)
            self.assertGreaterEqual(result.deleted_runs, 4)


if __name__ == "__main__":
    unittest.main()
