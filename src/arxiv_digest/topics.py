from __future__ import annotations

from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError("PyYAML is required. Install with: pip install -r requirements.txt") from exc

from .models import Topic


def load_topics(path: Path) -> list[Topic]:
    if not path.exists():
        raise FileNotFoundError(f"Topics config not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_topics = data.get("topics", [])
    topics: list[Topic] = []
    for item in raw_topics:
        key = str(item.get("key", "")).strip().lower()
        label = str(item.get("label", key)).strip()
        keywords = [str(x).strip().lower() for x in item.get("keywords", []) if str(x).strip()]
        categories = [str(x).strip() for x in item.get("categories", []) if str(x).strip()]
        must_have_phrases = [
            str(x).strip().lower()
            for x in item.get("must_have_phrases", [])
            if str(x).strip()
        ]
        exclude_keywords = [
            str(x).strip().lower()
            for x in item.get("exclude_keywords", [])
            if str(x).strip()
        ]
        if not key or not keywords or not categories:
            continue
        topics.append(
            Topic(
                key=key,
                label=label,
                keywords=keywords,
                categories=categories,
                must_have_phrases=must_have_phrases,
                exclude_keywords=exclude_keywords,
            )
        )
    return topics
