from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
import traceback
import uuid

from .arxiv_client import ArxivFetchConfig, fetch_topic_papers
from .config import AppConfig
from .emailer import render_email, send_email
from .housekeeping import run_housekeeping
from .models import Paper, PaperScore, Topic, utcnow
from .repository import Repository
from .scoring import select_top_k
from .summarizer import summarize_paper
from .time_utils import latest_arxiv_announcement_cutoff_utc
from .topics import load_topics


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    total_candidates: int
    total_selected: int
    output_text_path: Path | None
    output_html_path: Path | None


def run_digest(
    *,
    cfg: AppConfig,
    dry_run: bool,
    output_dir: Path,
) -> RunResult:
    run_id = uuid.uuid4().hex
    repo = Repository(cfg.db_path)
    repo.create_run(run_id, status="running", notes="starting")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        topics = load_topics(cfg.topics_config_path)
        if not topics:
            raise RuntimeError("No topics loaded from topics config.")

        if cfg.run_current_date_only:
            cutoff = latest_arxiv_announcement_cutoff_utc()
            print(
                f"[run:{run_id}] Using cutoff: {cutoff.isoformat()} "
                "(current-date mode, arXiv announcement boundary 20:00 America/New_York)"
            )
        else:
            use_last_success = cfg.run_use_last_success if not dry_run else cfg.dry_run_use_last_success
            if not use_last_success:
                cutoff = utcnow() - timedelta(hours=cfg.lookback_hours)
                mode = "dry-run" if dry_run else "run"
                print(
                    f"[run:{run_id}] Using cutoff: {cutoff.isoformat()} "
                    f"({mode} lookback window, {cfg.lookback_hours}h)"
                )
            else:
                last_success = repo.get_last_successful_run_time(include_dry_run=dry_run)
                if last_success is None:
                    cutoff = utcnow() - timedelta(hours=cfg.lookback_hours)
                else:
                    cutoff = last_success
                print(f"[run:{run_id}] Using cutoff: {cutoff.isoformat()} (last successful run logic)")

        lookback_cutoff = utcnow() - timedelta(hours=cfg.lookback_hours)
        if cfg.run_current_date_only:
            fetch_cutoff = cutoff
        else:
            fetch_cutoff = (
                lookback_cutoff
                if ((not dry_run) and cfg.run_use_last_success and cfg.run_fallback_to_lookback_if_empty)
                else cutoff
            )

        fetch_cfg = ArxivFetchConfig(
            max_results_per_topic=cfg.max_results_per_topic,
            timeout_seconds=cfg.request_timeout_seconds,
            user_agent=cfg.user_agent,
        )
        all_by_id: dict[str, Paper] = {}
        papers_for_topic: dict[str, list[Paper]] = {}

        print(f"[run:{run_id}] Step 2: Fetching candidate papers from arXiv (broad CS pool)")
        global_topic = Topic(
            key="_all_cs",
            label="All CS",
            keywords=["computer science"],
            categories=["cs.*"],
        )
        raw_pool = fetch_topic_papers(global_topic, fetch_cfg, cutoff=fetch_cutoff)
        if len(raw_pool) == 0:
            raise RuntimeError(
                "arXiv returned an empty candidate pool. "
                "This is usually a transient API/network issue; retry the run."
            )
        filtered_pool = [p for p in raw_pool if p.published_at >= cutoff or p.updated_at >= cutoff]
        if cfg.run_current_date_only and len(filtered_pool) == 0:
            # arXiv API timestamps can lag announcement windows; widen as a safety net.
            widened_hours = max(72, cfg.lookback_hours)
            widened_cutoff = utcnow() - timedelta(hours=widened_hours)
            widened_pool = [p for p in raw_pool if p.published_at >= widened_cutoff or p.updated_at >= widened_cutoff]
            if widened_pool:
                print(
                    f"[run:{run_id}] No candidates at announcement cutoff; "
                    f"widening to last {widened_hours}h for visibility."
                )
                filtered_pool = widened_pool
        if dry_run and (not cfg.run_current_date_only) and len(filtered_pool) == 0:
            # A strict rolling 24h window can miss the latest arXiv release window.
            widened_hours = max(72, cfg.lookback_hours)
            widened_cutoff = utcnow() - timedelta(hours=widened_hours)
            widened_pool = [p for p in raw_pool if p.published_at >= widened_cutoff or p.updated_at >= widened_cutoff]
            if widened_pool:
                print(
                    f"[run:{run_id}] No candidates in {cfg.lookback_hours}h window; "
                    f"widening dry-run to {widened_hours}h for visibility."
                )
                filtered_pool = widened_pool

        for paper in filtered_pool:
            all_by_id[paper.arxiv_id] = paper
        for topic in topics:
            papers_for_topic[topic.key] = filtered_pool
        print(
            f"[run:{run_id}]   fetched_pool={len(raw_pool)} "
            f"kept_after_cutoff={len(filtered_pool)}"
        )

        if (
            (not dry_run)
            and cfg.run_use_last_success
            and cfg.run_fallback_to_lookback_if_empty
            and len(all_by_id) == 0
        ):
            fallback_cutoff = utcnow() - timedelta(hours=cfg.lookback_hours)
            print(
                f"[run:{run_id}] No live candidates with last-success cutoff; "
                f"falling back to lookback window cutoff={fallback_cutoff.isoformat()}"
            )
            papers_for_topic = {}
            all_by_id = {}
            filtered_pool = [p for p in raw_pool if p.published_at >= fallback_cutoff or p.updated_at >= fallback_cutoff]
            for paper in filtered_pool:
                all_by_id[paper.arxiv_id] = paper
            for topic in topics:
                papers_for_topic[topic.key] = filtered_pool
            print(f"[run:{run_id}]   fallback kept_after_lookback={len(filtered_pool)}")

        repo.upsert_papers(all_by_id.values(), {})

        print(f"[run:{run_id}] Step 3: Computing per-keyword correlation and top-{cfg.top_k_per_keyword}")
        selected_scores_by_keyword: dict[str, list[PaperScore]] = {}
        all_scores_to_store: list[PaperScore] = []
        for topic in topics:
            candidates = papers_for_topic.get(topic.key, [])
            if (dry_run and cfg.dry_run_ignore_sent_log) or ((not dry_run) and cfg.run_ignore_sent_log):
                sent_ids = set()
            else:
                sent_ids = repo.get_sent_ids(topic.key)
            top_scores = select_top_k(
                topic=topic,
                papers=candidates,
                full_text_by_id={},
                k=cfg.top_k_per_keyword,
                excluded_ids=sent_ids,
            )
            selected_scores_by_keyword[topic.key] = top_scores
            all_scores_to_store.extend(top_scores)
            print(f"[run:{run_id}]   topic={topic.key} matched={len(top_scores)}")

        repo.clear_scores_for_run(run_id)
        repo.insert_scores(run_id, all_scores_to_store)

        print(f"[run:{run_id}] Step 4: Generating summaries")
        selected_ids = {score.arxiv_id for scores in selected_scores_by_keyword.values() for score in scores}
        summaries_by_id: dict[str, str] = {}
        for arxiv_id in selected_ids:
            paper = all_by_id[arxiv_id]
            summaries_by_id[arxiv_id] = summarize_paper(
                title=paper.title,
                abstract=paper.abstract,
                full_text="",
            )

        print(f"[run:{run_id}] Step 5: Rendering and sending email")
        payload = render_email(
            run_id=run_id,
            results_by_keyword=selected_scores_by_keyword,
            papers_by_id=all_by_id,
            summaries_by_id=summaries_by_id,
        )

        text_out = output_dir / f"{run_id}.txt"
        html_out = output_dir / f"{run_id}.html"
        text_out.write_text(payload.text_body, encoding="utf-8")
        html_out.write_text(payload.html_body, encoding="utf-8")

        total_selected = sum(len(v) for v in selected_scores_by_keyword.values())
        cleanup = run_housekeeping(cfg=cfg, output_dir=output_dir)
        cleanup_notes = (
            "cleanup: "
            f"output_files={cleanup.deleted_output_files}, "
            f"text_cache_files={cleanup.deleted_text_cache_entries}, "
            f"keyword_scores={cleanup.deleted_keyword_scores}, "
            f"sent_log={cleanup.deleted_sent_log_rows}, "
            f"runs={cleanup.deleted_runs}"
        )
        if dry_run:
            status = "success"
            notes = f"dry_run=1 candidates={len(all_by_id)} selected={total_selected}; {cleanup_notes}"
        else:
            if not cfg.email_to:
                raise RuntimeError("EMAIL_TO is empty; cannot send digest.")
            if not cfg.smtp_host:
                raise RuntimeError("SMTP_HOST is empty; cannot send digest.")

            email_from = cfg.email_from or cfg.smtp_username or cfg.email_to
            send_email(
                smtp_host=cfg.smtp_host,
                smtp_port=cfg.smtp_port,
                smtp_username=cfg.smtp_username,
                smtp_password=cfg.smtp_password,
                email_from=email_from,
                email_to=cfg.email_to,
                payload=payload,
                timeout_seconds=cfg.smtp_timeout_seconds,
                retries=cfg.smtp_retries,
                starttls=cfg.smtp_starttls,
                use_ssl=cfg.smtp_use_ssl,
                fallback_ssl=cfg.smtp_fallback_ssl,
            )
            for keyword, scores in selected_scores_by_keyword.items():
                for score in scores:
                    repo.mark_sent(run_id, keyword, score.arxiv_id)
            status = "success"
            notes = f"dry_run=0 candidates={len(all_by_id)} selected={total_selected}; {cleanup_notes}"

        repo.finalize_run(run_id, status=status, notes=notes)
        return RunResult(
            run_id=run_id,
            status=status,
            total_candidates=len(all_by_id),
            total_selected=total_selected,
            output_text_path=text_out,
            output_html_path=html_out,
        )
    except Exception as exc:
        message = f"{exc}\n{traceback.format_exc(limit=5)}"
        repo.finalize_run(run_id, status="failed", notes=message[:2000])
        raise
