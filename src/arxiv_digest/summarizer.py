from __future__ import annotations

from .text_utils import split_sentences

METHOD_HINTS = ("propose", "present", "introduce", "develop", "design", "build")
RESULT_HINTS = ("results", "outperform", "achieve", "improve", "state-of-the-art", "sota")


def _pick_sentences(candidates: list[str], limit: int = 4) -> list[str]:
    if not candidates:
        return []

    selected: list[str] = []
    selected.append(candidates[0])

    method = next((s for s in candidates[1:] if any(h in s.lower() for h in METHOD_HINTS)), None)
    if method and method not in selected:
        selected.append(method)

    result = next((s for s in candidates[1:] if any(h in s.lower() for h in RESULT_HINTS)), None)
    if result and result not in selected:
        selected.append(result)

    for sentence in candidates:
        if len(selected) >= limit:
            break
        if sentence not in selected:
            selected.append(sentence)
    return selected[:limit]


def summarize_paper(*, title: str, abstract: str, full_text: str) -> str:
    abstract_sentences = split_sentences(abstract)
    if not abstract_sentences:
        # fallback for missing abstract: use early full-text sentences
        intro_sentences = split_sentences(full_text[:3000])
        picked = _pick_sentences(intro_sentences, limit=3)
        return " ".join(picked)

    picked = _pick_sentences(abstract_sentences, limit=4)
    summary = " ".join(picked)
    if len(summary) < 220:
        intro_sentences = split_sentences(full_text[:2500])
        extra = [s for s in intro_sentences if s not in picked][:1]
        if extra:
            summary = f"{summary} {extra[0]}".strip()
    return summary

