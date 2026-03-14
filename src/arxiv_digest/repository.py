from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import Paper, PaperScore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_last_successful_run_time(self, *, include_dry_run: bool = False) -> datetime | None:
        where_extra = ""
        if not include_dry_run:
            # Ignore dry-run entries so test runs do not shift the live-run cutoff window.
            where_extra = "AND (notes IS NULL OR notes NOT LIKE 'dry_run=1%')"

        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT completed_at
                FROM runs
                WHERE status = 'success' AND completed_at IS NOT NULL
                {where_extra}
                ORDER BY completed_at DESC
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return None
        text = row["completed_at"]
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def create_run(self, run_id: str, status: str = "running", notes: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs(run_id, started_at, status, notes)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, _utc_now_iso(), status, notes),
            )
            conn.commit()

    def finalize_run(self, run_id: str, status: str, notes: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET completed_at = ?, status = ?, notes = ?
                WHERE run_id = ?
                """,
                (_utc_now_iso(), status, notes, run_id),
            )
            conn.commit()

    def upsert_papers(self, papers: Iterable[Paper], text_hash_map: dict[str, str]) -> None:
        with self._connect() as conn:
            for paper in papers:
                conn.execute(
                    """
                    INSERT INTO papers (
                        arxiv_id, title, abstract, paper_url, pdf_url, published_at, updated_at,
                        primary_category, categories_csv, extracted_text_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(arxiv_id) DO UPDATE SET
                        title = excluded.title,
                        abstract = excluded.abstract,
                        paper_url = excluded.paper_url,
                        pdf_url = excluded.pdf_url,
                        published_at = excluded.published_at,
                        updated_at = excluded.updated_at,
                        primary_category = excluded.primary_category,
                        categories_csv = excluded.categories_csv,
                        extracted_text_hash = excluded.extracted_text_hash
                    """,
                    (
                        paper.arxiv_id,
                        paper.title,
                        paper.abstract,
                        paper.paper_url,
                        paper.pdf_url,
                        paper.published_at.isoformat(),
                        paper.updated_at.isoformat(),
                        paper.primary_category,
                        ",".join(paper.categories),
                        text_hash_map.get(paper.arxiv_id, ""),
                    ),
                )
            conn.commit()

    def clear_scores_for_run(self, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM keyword_scores WHERE run_id = ?", (run_id,))
            conn.commit()

    def insert_scores(self, run_id: str, scores: Iterable[PaperScore]) -> None:
        with self._connect() as conn:
            for score in scores:
                payload = asdict(score)
                conn.execute(
                    """
                    INSERT INTO keyword_scores(
                        keyword, arxiv_id, title_corr, abstract_corr, full_text_corr,
                        category_bonus, total_corr, run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["keyword"],
                        payload["arxiv_id"],
                        payload["title_corr"],
                        payload["abstract_corr"],
                        payload["full_text_corr"],
                        payload["category_bonus"],
                        payload["total_corr"],
                        run_id,
                    ),
                )
            conn.commit()

    def get_sent_ids(self, keyword: str) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT arxiv_id FROM sent_log WHERE keyword = ?",
                (keyword,),
            ).fetchall()
        return {row["arxiv_id"] for row in rows}

    def mark_sent(self, run_id: str, keyword: str, arxiv_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sent_log(keyword, arxiv_id, sent_at, run_id)
                VALUES (?, ?, ?, ?)
                """,
                (keyword, arxiv_id, _utc_now_iso(), run_id),
            )
            conn.commit()
