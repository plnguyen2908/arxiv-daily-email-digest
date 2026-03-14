from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from arxiv_digest.emailer import render_email
from arxiv_digest.models import Paper, PaperScore
from arxiv_digest.summarizer import summarize_paper


class EmailAndSummaryTests(unittest.TestCase):
    def test_summary_not_empty(self) -> None:
        abstract = (
            "We propose a transformer-based method for document understanding. "
            "Our approach introduces efficient sparse attention. "
            "Results show improved accuracy on three benchmarks."
        )
        full_text = "Introduction. This paper presents additional implementation details."
        summary = summarize_paper(title="Doc model", abstract=abstract, full_text=full_text)
        self.assertIn("propose", summary.lower())
        self.assertTrue(len(summary) > 30)

    def test_email_contains_abstract_and_summary(self) -> None:
        dt = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
        paper = Paper(
            arxiv_id="2603.00001",
            title="Example Paper",
            abstract="This paper studies multimodal learning.",
            authors=["A. Author", "B. Author"],
            published_at=dt,
            updated_at=dt,
            paper_url="https://arxiv.org/abs/2603.00001",
            pdf_url="https://arxiv.org/pdf/2603.00001.pdf",
            primary_category="cs.AI",
            categories=["cs.AI"],
        )
        score = PaperScore(
            keyword="ai",
            arxiv_id=paper.arxiv_id,
            title_corr=0.5,
            abstract_corr=0.6,
            full_text_corr=0.7,
            category_bonus=1.0,
            total_corr=0.7,
        )
        payload = render_email(
            run_id="abc123",
            results_by_keyword={"ai": [score]},
            papers_by_id={paper.arxiv_id: paper},
            summaries_by_id={paper.arxiv_id: "The paper proposes a new multimodal method."},
        )
        self.assertIn("Abstract:", payload.text_body)
        self.assertIn("Summary:", payload.text_body)
        self.assertIn("<strong>Abstract:</strong>", payload.html_body)
        self.assertIn("<strong>Summary:</strong>", payload.html_body)


if __name__ == "__main__":
    unittest.main()

