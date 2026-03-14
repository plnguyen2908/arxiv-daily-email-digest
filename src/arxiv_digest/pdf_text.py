from __future__ import annotations

import hashlib
import io
from pathlib import Path
import time
from typing import Tuple

import requests

try:
    from pypdf import PdfReader
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError("pypdf is required. Install with: pip install -r requirements.txt") from exc

from .text_utils import normalize_space


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _sanitize_file_component(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)
    return clean.strip("_") or "paper"


def extract_pdf_text_from_bytes(pdf_bytes: bytes) -> str:
    # pypdf supports reading from bytes directly.
    reader = PdfReader(io.BytesIO(pdf_bytes))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    return normalize_space("\n".join(chunks))


def fetch_and_extract_pdf_text(pdf_url: str, timeout_seconds: int, user_agent: str) -> str:
    if not pdf_url:
        return ""
    response = None
    for attempt in range(3):
        try:
            response = requests.get(pdf_url, timeout=timeout_seconds, headers={"User-Agent": user_agent})
            response.raise_for_status()
            break
        except requests.RequestException:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    if response is None:
        return ""
    content_type = (response.headers.get("Content-Type", "") or "").lower()
    if "pdf" not in content_type and not pdf_url.lower().endswith(".pdf"):
        return ""
    return extract_pdf_text_from_bytes(response.content)


def load_or_fetch_text(
    *,
    cache_dir: Path,
    cache_key: str,
    pdf_url: str,
    timeout_seconds: int,
    user_agent: str,
) -> Tuple[str, str]:
    """Return extracted text and hash, using local cache when available."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_key = _sanitize_file_component(cache_key)
    text_path = cache_dir / f"{safe_key}.txt"
    hash_path = cache_dir / f"{safe_key}.sha256"

    if text_path.exists():
        text = text_path.read_text(encoding="utf-8")
        if text.strip():
            digest = hash_path.read_text(encoding="utf-8").strip() if hash_path.exists() else text_hash(text)
            return text, digest

    text = fetch_and_extract_pdf_text(
        pdf_url=pdf_url,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
    )
    digest = text_hash(text)
    if text.strip():
        text_path.write_text(text, encoding="utf-8")
        hash_path.write_text(digest, encoding="utf-8")
    return text, digest
