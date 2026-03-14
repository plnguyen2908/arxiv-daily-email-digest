from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from arxiv_digest.models import Paper, Topic
from arxiv_digest.scoring import category_bonus, correlation_score, select_top_k


def _paper(arxiv_id: str, title: str, abstract: str, primary: str, published_day: int) -> Paper:
    dt = datetime(2026, 3, published_day, 12, 0, tzinfo=timezone.utc)
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=["A. Author"],
        published_at=dt,
        updated_at=dt,
        paper_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        primary_category=primary,
        categories=[primary],
    )


class ScoringTests(unittest.TestCase):
    def test_correlation_score_overlap(self) -> None:
        self.assertGreater(correlation_score("machine learning", "new machine learning method"), 0.0)
        self.assertEqual(correlation_score("vision", ""), 0.0)

    def test_category_bonus(self) -> None:
        topic = Topic(key="ml", label="ML", keywords=["machine learning"], categories=["cs.LG", "stat.ML"])
        p1 = _paper("a1", "title", "abs", "cs.LG", 1)
        p2 = _paper("a2", "title", "abs", "cs.CV", 1)
        p2 = Paper(
            arxiv_id=p2.arxiv_id,
            title=p2.title,
            abstract=p2.abstract,
            authors=p2.authors,
            published_at=p2.published_at,
            updated_at=p2.updated_at,
            paper_url=p2.paper_url,
            pdf_url=p2.pdf_url,
            primary_category=p2.primary_category,
            categories=["cs.CV", "stat.ML"],
        )
        self.assertEqual(category_bonus(topic, p1), 0.0)
        self.assertEqual(category_bonus(topic, p2), 0.0)

    def test_select_top_k_excludes_sent(self) -> None:
        topic = Topic(key="nlp", label="NLP", keywords=["language", "text"], categories=["cs.CL"])
        p1 = _paper("1", "language model", "text understanding", "cs.CL", 10)
        p2 = _paper("2", "text retrieval baseline", "tabular text data", "cs.LG", 11)
        texts = {"1": "language text semantics", "2": "trees and features"}
        result = select_top_k(topic, [p1, p2], texts, k=5, excluded_ids={"1"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].arxiv_id, "2")

    def test_select_top_k_keyword_filter(self) -> None:
        topic = Topic(
            key="world_model",
            label="World Model",
            keywords=["world model", "world dynamics"],
            categories=["cs.*"],
        )
        p1 = _paper("1", "World Model for Planning", "We learn world dynamics.", "cs.LG", 10)
        p2 = _paper("2", "Ergodicity in reinforcement learning", "No latent-state modeling phrase.", "cs.LG", 11)
        texts = {"1": "world model world dynamics latent state", "2": "policy optimization and value function"}
        result = select_top_k(topic, [p1, p2], texts, k=5, excluded_ids=set())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].arxiv_id, "1")

    def test_keyword_filter_not_from_full_text_only(self) -> None:
        topic = Topic(
            key="world_model",
            label="World Model",
            keywords=["world model"],
            categories=["cs.*"],
        )
        p = _paper("3", "Policy Gradient for RL", "No world-model phrasing here.", "cs.LG", 12)
        texts = {"3": "related work mentions world model multiple times"}
        result = select_top_k(topic, [p], texts, k=5, excluded_ids=set())
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main()
