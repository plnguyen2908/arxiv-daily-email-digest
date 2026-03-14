from __future__ import annotations

import re
from collections import Counter

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall((text or "").lower())


def term_frequency(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = float(len(tokens))
    return {term: count / total for term, count in counts.items()}


def split_sentences(text: str) -> list[str]:
    clean = normalize_space(text)
    if not clean:
        return []
    return [x.strip() for x in SENTENCE_SPLIT_PATTERN.split(clean) if x.strip()]

