from __future__ import annotations

import math
import re
from datetime import datetime

from .models import Paper, PaperScore, Topic
from .text_utils import term_frequency, tokenize


def correlation_score(query_text: str, doc_text: str) -> float:
    """Cosine correlation over normalized term-frequency vectors."""
    q_tokens = tokenize(query_text)
    d_tokens = tokenize(doc_text)
    if not q_tokens or not d_tokens:
        return 0.0

    q_tf = term_frequency(q_tokens)
    d_tf = term_frequency(d_tokens)
    vocab = set(q_tf) | set(d_tf)

    dot = sum(q_tf.get(t, 0.0) * d_tf.get(t, 0.0) for t in vocab)
    q_norm = math.sqrt(sum(v * v for v in q_tf.values()))
    d_norm = math.sqrt(sum(v * v for v in d_tf.values()))
    if q_norm == 0.0 or d_norm == 0.0:
        return 0.0
    return dot / (q_norm * d_norm)


def category_bonus(topic: Topic, paper: Paper) -> float:
    # Simplified pipeline: do not use category bonus for ranking.
    return 0.0


def score_paper(topic: Topic, paper: Paper, full_text: str) -> PaperScore:
    query = " ".join(topic.keywords)
    title_corr = correlation_score(query, paper.title)
    abstract_corr = correlation_score(query, paper.abstract)
    full_text_corr = 0.0
    cat_bonus = 0.0
    total = (0.45 * title_corr) + (0.55 * abstract_corr)

    return PaperScore(
        keyword=topic.key,
        arxiv_id=paper.arxiv_id,
        title_corr=title_corr,
        abstract_corr=abstract_corr,
        full_text_corr=full_text_corr,
        category_bonus=cat_bonus,
        total_corr=total,
    )


def select_top_k(
    topic: Topic,
    papers: list[Paper],
    full_text_by_id: dict[str, str],
    k: int,
    excluded_ids: set[str],
) -> list[PaperScore]:
    def _keyword_present(haystack: str, keyword: str) -> bool:
        kword = (keyword or "").strip().lower()
        if not kword:
            return False
        if " " in kword or "-" in kword:
            return kword in haystack
        return re.search(rf"\b{re.escape(kword)}\b", haystack) is not None

    scored: list[tuple[PaperScore, datetime]] = []
    for paper in papers:
        if paper.arxiv_id in excluded_ids:
            continue
        haystack = f"{paper.title}\n{paper.abstract}".lower()
        if not any(_keyword_present(haystack, kw) for kw in topic.keywords):
            continue
        score = score_paper(topic, paper, "")
        scored.append((score, paper.published_at))

    scored.sort(
        key=lambda item: (
            -item[0].total_corr,
            -item[1].timestamp(),
            item[0].arxiv_id,
        )
    )
    if k <= 0:
        return [item[0] for item in scored]
    return [item[0] for item in scored[:k]]
