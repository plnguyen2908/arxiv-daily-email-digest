from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from arxiv_digest.arxiv_client import ArxivFetchConfig, fetch_topic_papers
from arxiv_digest.config import load_config
from arxiv_digest.models import Paper, Topic
from arxiv_digest.scoring import select_top_k
from arxiv_digest.summarizer import summarize_paper
from arxiv_digest.topics import load_topics


class FetchRequest(BaseModel):
    date: str | None = None
    force: bool = False


class ToggleDoneRequest(BaseModel):
    topic_key: str
    arxiv_id: str
    done: bool = True


class TopicPayload(BaseModel):
    key: str
    label: str
    keywords: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=lambda: ["cs.*"])
    must_have_phrases: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class TopicsUpdateRequest(BaseModel):
    topics: list[TopicPayload]


def _settings() -> dict[str, Any]:
    data_root = PROJECT_ROOT / os.getenv("UI_DATA_DIR", "data/ui_store")
    return {
        "timezone": os.getenv("RUN_TIMEZONE", "America/Chicago"),
        "topics_path": PROJECT_ROOT / os.getenv("TOPICS_CONFIG_PATH", "config/topics.yaml"),
        "data_root": data_root,
        "digests_dir": data_root / "digests",
        "max_data_bytes": max(1, int(os.getenv("UI_MAX_DATA_MB", "500"))) * 1024 * 1024,
        "fallback_days": max(1, int(os.getenv("UI_FETCH_FALLBACK_DAYS", "1"))),
    }


def _today_local(tz_name: str) -> date:
    zone = ZoneInfo(tz_name)
    return datetime.now(timezone.utc).astimezone(zone).date()


def _parse_date_or_400(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must use YYYY-MM-DD") from exc


def _window_utc(target_date: date, tz_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(tz_name)
    start_local = datetime.combine(target_date, datetime.min.time(), tzinfo=zone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _digest_path(digests_dir: Path, digest_date: date) -> Path:
    return digests_dir / f"{digest_date.isoformat()}.json"


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _enforce_disk_budget(digests_dir: Path, max_bytes: int) -> list[str]:
    digests_dir.mkdir(parents=True, exist_ok=True)
    removed: list[str] = []
    current = _dir_size_bytes(digests_dir)
    if current <= max_bytes:
        return removed

    files = sorted([p for p in digests_dir.glob("*.json") if p.is_file()], key=lambda p: p.stat().st_mtime)
    for file_path in files:
        if current <= max_bytes:
            break
        size = file_path.stat().st_size
        file_path.unlink(missing_ok=True)
        current -= size
        removed.append(file_path.name)
    return removed


def _load_digest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _save_digest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _digest_stats(payload: dict[str, Any]) -> dict[str, int | bool]:
    total = 0
    done = 0
    for topic in payload.get("topics", []):
        for paper in topic.get("papers", []):
            total += 1
            if bool(paper.get("done", False)):
                done += 1
    remaining = max(0, total - done)
    return {
        "total": total,
        "done": done,
        "remaining": remaining,
        "cleared": remaining == 0,
    }


def _topics_as_payload(topics: list[Topic]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for topic in topics:
        out.append(
            {
                "key": topic.key,
                "label": topic.label,
                "keywords": topic.keywords,
                "categories": topic.categories,
                "must_have_phrases": topic.must_have_phrases,
                "exclude_keywords": topic.exclude_keywords,
            }
        )
    return out


def _build_digest_for_date(target_date: date, settings: dict[str, Any]) -> dict[str, Any]:
    app_cfg = load_config(PROJECT_ROOT)
    topics = load_topics(settings["topics_path"])
    start_utc, end_utc = _window_utc(target_date, settings["timezone"])

    fetch_cfg = ArxivFetchConfig(
        max_results_per_topic=app_cfg.max_results_per_topic,
        timeout_seconds=app_cfg.request_timeout_seconds,
        user_agent=app_cfg.user_agent,
    )

    global_topic = Topic(
        key="_all_cs",
        label="All CS",
        keywords=["computer science"],
        categories=["cs.*"],
    )

    # Fetch slightly before the requested day to avoid missing entries due to API ordering/timezone shifts.
    raw_pool = fetch_topic_papers(global_topic, fetch_cfg, cutoff=start_utc - timedelta(days=2))

    by_id: dict[str, Paper] = {}
    for paper in raw_pool:
        in_window = (start_utc <= paper.published_at < end_utc) or (start_utc <= paper.updated_at < end_utc)
        if in_window:
            by_id[paper.arxiv_id] = paper

    day_papers = list(by_id.values())

    topics_out: list[dict[str, Any]] = []
    for topic in topics:
        scores = select_top_k(
            topic=topic,
            papers=day_papers,
            full_text_by_id={},
            k=0,
            excluded_ids=set(),
        )
        papers_out: list[dict[str, Any]] = []
        for score in scores:
            paper = by_id[score.arxiv_id]
            papers_out.append(
                {
                    "arxiv_id": paper.arxiv_id,
                    "title": paper.title,
                    "abstract": paper.abstract,
                    "summary": summarize_paper(title=paper.title, abstract=paper.abstract, full_text=""),
                    "paper_url": paper.paper_url,
                    "published_at": paper.published_at.isoformat(),
                    "updated_at": paper.updated_at.isoformat(),
                    "score": round(score.total_corr, 6),
                    "done": False,
                }
            )
        topics_out.append(
            {
                "key": topic.key,
                "label": topic.label,
                "papers": papers_out,
            }
        )

    payload = {
        "date": target_date.isoformat(),
        "timezone": settings["timezone"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topics": topics_out,
    }
    payload["stats"] = _digest_stats(payload)
    return payload


def _load_topics_yaml(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    topics = raw.get("topics", [])
    return topics if isinstance(topics, list) else []


def _save_topics_yaml(path: Path, topics: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"topics": topics}
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    path.write_text(text, encoding="utf-8")


app = FastAPI(title="arXiv Interactive Digest API", version="1.0.0")

origins_raw = os.getenv("CORS_ORIGINS", "*").strip()
if origins_raw == "*":
    allow_origins = ["*"]
    allow_credentials = False
else:
    allow_origins = [item.strip() for item in origins_raw.split(",") if item.strip()]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    cfg = _settings()
    cfg["digests_dir"].mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
def health() -> dict[str, Any]:
    cfg = _settings()
    return {
        "ok": True,
        "timezone": cfg["timezone"],
        "digests_dir": str(cfg["digests_dir"]),
        "data_used_bytes": _dir_size_bytes(cfg["digests_dir"]),
        "max_data_bytes": cfg["max_data_bytes"],
    }


@app.get("/api/topics")
def get_topics() -> dict[str, Any]:
    cfg = _settings()
    topics = _load_topics_yaml(cfg["topics_path"])
    return {"topics": topics}


@app.put("/api/topics")
def put_topics(req: TopicsUpdateRequest) -> dict[str, Any]:
    cfg = _settings()
    topics_out: list[dict[str, Any]] = []
    for topic in req.topics:
        key = topic.key.strip().lower()
        label = topic.label.strip() or key
        keywords = [x.strip().lower() for x in topic.keywords if x.strip()]
        categories = [x.strip() for x in topic.categories if x.strip()]
        if not key or not keywords:
            continue
        if not categories:
            categories = ["cs.*"]
        topics_out.append(
            {
                "key": key,
                "label": label,
                "keywords": keywords,
                "categories": categories,
                "must_have_phrases": [x.strip().lower() for x in topic.must_have_phrases if x.strip()],
                "exclude_keywords": [x.strip().lower() for x in topic.exclude_keywords if x.strip()],
            }
        )

    if not topics_out:
        raise HTTPException(status_code=400, detail="No valid topics provided")

    _save_topics_yaml(cfg["topics_path"], topics_out)
    return {"status": "ok", "topics": topics_out}


@app.get("/api/dates")
def list_dates() -> dict[str, Any]:
    cfg = _settings()
    entries: list[dict[str, Any]] = []
    for file_path in sorted(cfg["digests_dir"].glob("*.json"), reverse=True):
        try:
            payload = _load_digest(file_path)
        except Exception:
            continue
        stats = _digest_stats(payload)
        entries.append(
            {
                "date": payload.get("date", file_path.stem),
                "generated_at": payload.get("generated_at", ""),
                "stats": stats,
            }
        )
    return {"dates": entries}


@app.get("/api/digest/{digest_date}")
def get_digest(digest_date: str) -> dict[str, Any]:
    cfg = _settings()
    target_date = _parse_date_or_400(digest_date)
    path = _digest_path(cfg["digests_dir"], target_date)
    if not path.exists():
        payload = {
            "date": target_date.isoformat(),
            "timezone": cfg["timezone"],
            "generated_at": "",
            "topics": [],
        }
        payload["stats"] = _digest_stats(payload)
        return payload
    payload = _load_digest(path)
    payload["stats"] = _digest_stats(payload)
    return payload


@app.post("/api/fetch")
def fetch_digest(req: FetchRequest) -> dict[str, Any]:
    cfg = _settings()
    removed = _enforce_disk_budget(cfg["digests_dir"], cfg["max_data_bytes"])

    requested_date = _today_local(cfg["timezone"]) if not req.date else _parse_date_or_400(req.date)

    last_payload: dict[str, Any] | None = None
    resolved_date = requested_date
    fallback_days = 0
    from_cache = False

    for offset in range(cfg["fallback_days"] + 1):
        candidate = requested_date - timedelta(days=offset)
        resolved_date = candidate
        path = _digest_path(cfg["digests_dir"], candidate)

        if path.exists() and not req.force:
            payload = _load_digest(path)
            payload["stats"] = _digest_stats(payload)
            if int(payload["stats"]["total"]) > 0:
                last_payload = payload
                fallback_days = offset
                from_cache = True
                break

        payload = _build_digest_for_date(candidate, cfg)
        _save_digest(path, payload)
        payload["stats"] = _digest_stats(payload)
        last_payload = payload
        fallback_days = offset
        if int(payload["stats"]["total"]) > 0:
            break

    if last_payload is None:
        raise HTTPException(status_code=500, detail="Unable to build digest")

    return {
        "status": "ok",
        "requested_date": requested_date.isoformat(),
        "resolved_date": resolved_date.isoformat(),
        "fallback_days": fallback_days,
        "from_cache": from_cache,
        "deleted_old_dates": removed,
        "digest": last_payload,
    }


@app.post("/api/digest/{digest_date}/toggle")
def toggle_done(digest_date: str, req: ToggleDoneRequest) -> dict[str, Any]:
    cfg = _settings()
    target_date = _parse_date_or_400(digest_date)
    path = _digest_path(cfg["digests_dir"], target_date)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No digest for this date")

    payload = _load_digest(path)
    matched = False
    for topic in payload.get("topics", []):
        if topic.get("key") != req.topic_key:
            continue
        for paper in topic.get("papers", []):
            if paper.get("arxiv_id") == req.arxiv_id:
                paper["done"] = bool(req.done)
                matched = True
                break
        if matched:
            break

    if not matched:
        raise HTTPException(status_code=404, detail="Paper not found in date/topic")

    payload["stats"] = _digest_stats(payload)
    _save_digest(path, payload)
    return {
        "status": "ok",
        "date": digest_date,
        "stats": payload["stats"],
    }
