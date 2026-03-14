from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from arxiv_digest.db import init_db
from arxiv_digest.models import Paper, PaperScore
from arxiv_digest.repository import Repository


class RepositoryTests(unittest.TestCase):
    def test_sent_log_and_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_db(db_path)
            repo = Repository(db_path)

            dt = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
            paper = Paper(
                arxiv_id="2603.00042",
                title="Test",
                abstract="Abstract",
                authors=["A"],
                published_at=dt,
                updated_at=dt,
                paper_url="https://arxiv.org/abs/2603.00042",
                pdf_url="https://arxiv.org/pdf/2603.00042.pdf",
                primary_category="cs.AI",
                categories=["cs.AI"],
            )
            repo.upsert_papers([paper], text_hash_map={paper.arxiv_id: "h1"})

            run_id = "run1"
            repo.create_run(run_id, "running", "")
            score = PaperScore(
                keyword="ai",
                arxiv_id=paper.arxiv_id,
                title_corr=0.1,
                abstract_corr=0.2,
                full_text_corr=0.3,
                category_bonus=1.0,
                total_corr=0.5,
            )
            repo.insert_scores(run_id, [score])
            repo.mark_sent(run_id, "ai", paper.arxiv_id)
            repo.finalize_run(run_id, "success", "ok")

            self.assertIn(paper.arxiv_id, repo.get_sent_ids("ai"))

            with sqlite3.connect(db_path) as conn:
                total_scores = conn.execute("SELECT COUNT(*) FROM keyword_scores").fetchone()[0]
                self.assertEqual(total_scores, 1)


if __name__ == "__main__":
    unittest.main()

