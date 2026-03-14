from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from .models import Paper, Topic
from .text_utils import normalize_space

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ARXIV_API_URL = "https://export.arxiv.org/api/query"


@dataclass(frozen=True)
class ArxivFetchConfig:
    max_results_per_topic: int
    timeout_seconds: int
    user_agent: str


def _parse_dt(value: str) -> datetime:
    # Example: 2026-03-11T19:58:23Z
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _extract_arxiv_id(raw_id: str) -> str:
    value = (raw_id or "").strip().rstrip("/")
    return value.split("/")[-1]


def _query_for_categories(categories: list[str]) -> str:
    clauses: list[str] = []
    for cat in categories:
        clean = (cat or "").strip()
        if not clean:
            continue
        clauses.append(f"cat:{clean}")
        # For wildcard like cs.* add a prefix fallback cat:cs to improve robustness.
        if clean.endswith(".*"):
            prefix = clean[:-2]
            if prefix:
                clauses.append(f"cat:{prefix}")
    # de-dup while keeping order
    seen: set[str] = set()
    ordered = []
    for c in clauses:
        if c in seen:
            continue
        seen.add(c)
        ordered.append(c)
    return " OR ".join(ordered)


def _parse_entry(entry: ET.Element) -> Paper:
    raw_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
    arxiv_id = _extract_arxiv_id(raw_id)
    title = normalize_space(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
    abstract = normalize_space(entry.findtext("atom:summary", default="", namespaces=ATOM_NS))
    published = _parse_dt(entry.findtext("atom:published", default="1970-01-01T00:00:00Z", namespaces=ATOM_NS))
    updated = _parse_dt(entry.findtext("atom:updated", default="1970-01-01T00:00:00Z", namespaces=ATOM_NS))
    authors = [
        normalize_space(author.findtext("atom:name", default="", namespaces=ATOM_NS))
        for author in entry.findall("atom:author", ATOM_NS)
        if normalize_space(author.findtext("atom:name", default="", namespaces=ATOM_NS))
    ]
    categories = [cat.attrib.get("term", "") for cat in entry.findall("atom:category", ATOM_NS)]
    primary_category = entry.find("arxiv:primary_category", ATOM_NS)
    primary_category_term = primary_category.attrib.get("term", "") if primary_category is not None else ""

    paper_url = ""
    pdf_url = ""
    for link in entry.findall("atom:link", ATOM_NS):
        href = link.attrib.get("href", "")
        title_attr = link.attrib.get("title", "")
        rel = link.attrib.get("rel", "")
        type_attr = link.attrib.get("type", "")
        if title_attr == "pdf":
            pdf_url = href
        if rel == "alternate" and type_attr == "text/html":
            paper_url = href

    if not paper_url:
        paper_url = raw_id
    if not pdf_url and arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        published_at=published,
        updated_at=updated,
        paper_url=paper_url,
        pdf_url=pdf_url,
        primary_category=primary_category_term,
        categories=[x for x in categories if x],
    )


def fetch_topic_papers(
    topic: Topic,
    cfg: ArxivFetchConfig,
    cutoff: datetime | None = None,
) -> list[Paper]:
    query = _query_for_categories(topic.categories)
    headers = {"User-Agent": cfg.user_agent}
    page_size = max(1, cfg.max_results_per_topic)
    start = 0
    papers: list[Paper] = []

    while True:
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": str(start),
            "max_results": str(page_size),
        }
        url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

        last_error: Exception | None = None
        response = None
        for attempt in range(3):
            try:
                response = requests.get(url, timeout=cfg.timeout_seconds, headers=headers)
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        if response is None:
            message = (
                f"arXiv fetch failed for topic={topic.key}. "
                f"Likely network/DNS issue reaching export.arxiv.org. "
                f"Original error: {last_error}"
            )
            raise RuntimeError(message) from last_error

        root = ET.fromstring(response.text)
        page_papers: list[Paper] = []
        for entry in root.findall("atom:entry", ATOM_NS):
            paper = _parse_entry(entry)
            if paper.arxiv_id:
                page_papers.append(paper)

        if not page_papers:
            break
        papers.extend(page_papers)

        # Results are sorted by submittedDate descending. If the oldest paper in
        # this page is already older than cutoff, all later pages will be older.
        if cutoff is not None:
            oldest = page_papers[-1]
            if oldest.published_at < cutoff and oldest.updated_at < cutoff:
                break

        # No more pages.
        if len(page_papers) < page_size:
            break
        start += page_size

    return papers
