from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from .config import AppConfig


@dataclass(frozen=True)
class CleanupResult:
    deleted_output_files: int
    deleted_text_cache_entries: int
    deleted_keyword_scores: int
    deleted_sent_log_rows: int
    deleted_runs: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _delete_old_files_by_age(files: list[Path], retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    cutoff = _utc_now() - timedelta(days=retention_days)
    deleted = 0
    for file_path in files:
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                file_path.unlink(missing_ok=True)
                deleted += 1
        except FileNotFoundError:
            continue
    return deleted


def _delete_excess_files(files: list[Path], max_files: int) -> int:
    if max_files <= 0:
        return 0
    files_sorted = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    extra = files_sorted[max_files:]
    deleted = 0
    for file_path in extra:
        try:
            file_path.unlink(missing_ok=True)
            deleted += 1
        except FileNotFoundError:
            continue
    return deleted


def cleanup_output_dir(output_dir: Path, retention_days: int, max_files: int) -> int:
    if not output_dir.exists():
        return 0
    files = [p for p in output_dir.iterdir() if p.is_file()]
    deleted = _delete_old_files_by_age(files, retention_days)
    files = [p for p in output_dir.iterdir() if p.is_file()]
    deleted += _delete_excess_files(files, max_files)
    return deleted


def cleanup_text_cache(cache_dir: Path, retention_days: int, max_entries: int) -> int:
    if not cache_dir.exists():
        return 0

    groups: dict[str, list[Path]] = {}
    for file_path in cache_dir.iterdir():
        if not file_path.is_file():
            continue
        stem = file_path.stem
        if stem.endswith(".sha256"):
            stem = stem[: -len(".sha256")]
        groups.setdefault(stem, []).append(file_path)

    if not groups:
        return 0

    cutoff = _utc_now() - timedelta(days=max(retention_days, 1))
    deleted = 0
    keep: list[tuple[str, float]] = []
    for stem, files in groups.items():
        newest_mtime = max(p.stat().st_mtime for p in files)
        newest_dt = datetime.fromtimestamp(newest_mtime, tz=timezone.utc)
        if retention_days > 0 and newest_dt < cutoff:
            for p in files:
                p.unlink(missing_ok=True)
                deleted += 1
        else:
            keep.append((stem, newest_mtime))

    if max_entries > 0 and len(keep) > max_entries:
        keep.sort(key=lambda item: item[1], reverse=True)
        to_remove = keep[max_entries:]
        for stem, _ in to_remove:
            for p in groups.get(stem, []):
                p.unlink(missing_ok=True)
                deleted += 1
    return deleted


def _trim_table_by_limit(conn: sqlite3.Connection, table: str, id_col: str, limit: int) -> int:
    if limit <= 0:
        return 0
    current = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if current <= limit:
        return 0
    conn.execute(
        f"""
        DELETE FROM {table}
        WHERE {id_col} NOT IN (
            SELECT {id_col}
            FROM {table}
            ORDER BY {id_col} DESC
            LIMIT ?
        )
        """,
        (limit,),
    )
    return current - limit


def cleanup_db(db_path: Path, cfg: AppConfig) -> tuple[int, int, int]:
    if not db_path.exists():
        return (0, 0, 0)

    with sqlite3.connect(db_path) as conn:
        deleted_scores = _trim_table_by_limit(
            conn, table="keyword_scores", id_col="id", limit=cfg.db_max_keyword_scores
        )
        deleted_sent = _trim_table_by_limit(
            conn, table="sent_log", id_col="id", limit=cfg.db_max_sent_log_rows
        )

        deleted_runs = 0
        if cfg.db_max_runs > 0:
            total_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            if total_runs > cfg.db_max_runs:
                conn.execute(
                    """
                    DELETE FROM runs
                    WHERE run_id NOT IN (
                        SELECT run_id
                        FROM runs
                        ORDER BY started_at DESC
                        LIMIT ?
                    )
                    """,
                    (cfg.db_max_runs,),
                )
                deleted_runs = total_runs - cfg.db_max_runs

        conn.commit()
    return (deleted_scores, deleted_sent, deleted_runs)


def run_housekeeping(cfg: AppConfig, output_dir: Path) -> CleanupResult:
    deleted_output = cleanup_output_dir(
        output_dir=output_dir,
        retention_days=cfg.output_retention_days,
        max_files=cfg.max_output_files,
    )
    deleted_cache = cleanup_text_cache(
        cache_dir=cfg.text_cache_dir,
        retention_days=cfg.text_cache_retention_days,
        max_entries=cfg.max_text_cache_files,
    )
    deleted_scores, deleted_sent, deleted_runs = cleanup_db(cfg.db_path, cfg)

    return CleanupResult(
        deleted_output_files=deleted_output,
        deleted_text_cache_entries=deleted_cache,
        deleted_keyword_scores=deleted_scores,
        deleted_sent_log_rows=deleted_sent,
        deleted_runs=deleted_runs,
    )
