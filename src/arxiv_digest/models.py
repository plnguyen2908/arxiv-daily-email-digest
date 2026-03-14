from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Topic:
    key: str
    label: str
    keywords: list[str]
    categories: list[str]
    must_have_phrases: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    published_at: datetime
    updated_at: datetime
    paper_url: str
    pdf_url: str
    primary_category: str
    categories: list[str]


@dataclass(frozen=True)
class PaperScore:
    keyword: str
    arxiv_id: str
    title_corr: float
    abstract_corr: float
    full_text_corr: float
    category_bonus: float
    total_corr: float


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
