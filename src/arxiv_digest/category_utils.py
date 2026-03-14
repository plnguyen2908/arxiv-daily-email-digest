from __future__ import annotations


def category_pattern_matches(pattern: str, category: str) -> bool:
    p = (pattern or "").strip()
    c = (category or "").strip()
    if not p or not c:
        return False
    if p.endswith(".*"):
        prefix = p[:-1]  # keep trailing dot, e.g. "cs."
        return c.startswith(prefix)
    return p == c


def matches_any_category_pattern(patterns: list[str], category: str) -> bool:
    return any(category_pattern_matches(p, category) for p in patterns)

