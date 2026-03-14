from __future__ import annotations

import html
import socket
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage

from .models import Paper, PaperScore


@dataclass(frozen=True)
class EmailPayload:
    subject: str
    text_body: str
    html_body: str


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def render_email(
    *,
    run_id: str,
    results_by_keyword: dict[str, list[PaperScore]],
    papers_by_id: dict[str, Paper],
    summaries_by_id: dict[str, str],
) -> EmailPayload:
    subject = f"arXiv Digest ({run_id[:8]})"
    text_lines = [subject, "", "Per-keyword matched papers (last 24h):"]
    html_parts = [
        "<html><body>",
        f"<h2>{html.escape(subject)}</h2>",
        "<p>Per-keyword matched papers (last 24h) with abstract, summary, and correlation scores.</p>",
    ]

    for keyword in sorted(results_by_keyword):
        scores = results_by_keyword[keyword]
        text_lines.extend(["", f"## {keyword.upper()}"])
        html_parts.append(f"<h3>{html.escape(keyword.upper())}</h3>")
        html_parts.append("<ol>")
        for score in scores:
            paper = papers_by_id[score.arxiv_id]
            summary = summaries_by_id.get(score.arxiv_id, "")
            authors = ", ".join(paper.authors) if paper.authors else "Unknown"
            date_text = _fmt_date(paper.published_at)

            text_lines.extend(
                [
                    f"- {paper.title}",
                    f"  URL: {paper.paper_url}",
                    f"  Authors: {authors}",
                    f"  Published: {date_text}",
                    (
                        "  Scores: "
                        f"title={score.title_corr:.3f}, "
                        f"abstract={score.abstract_corr:.3f}, "
                        f"total={score.total_corr:.3f}"
                    ),
                    f"  Abstract: {paper.abstract}",
                    f"  Summary: {summary}",
                    "",
                ]
            )

            html_parts.append("<li>")
            html_parts.append(
                f"<p><a href=\"{html.escape(paper.paper_url)}\"><strong>{html.escape(paper.title)}</strong></a><br>"
                f"Authors: {html.escape(authors)}<br>"
                f"Published: {html.escape(date_text)}<br>"
                f"Scores: title={score.title_corr:.3f}, abstract={score.abstract_corr:.3f}, "
                f"total={score.total_corr:.3f}</p>"
            )
            html_parts.append(f"<p><strong>Abstract:</strong> {html.escape(paper.abstract)}</p>")
            html_parts.append(f"<p><strong>Summary:</strong> {html.escape(summary)}</p>")
            html_parts.append("</li>")
        html_parts.append("</ol>")

    html_parts.append("</body></html>")
    text_body = "\n".join(text_lines).strip() + "\n"
    html_body = "".join(html_parts)
    return EmailPayload(subject=subject, text_body=text_body, html_body=html_body)


def send_email(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    email_from: str,
    email_to: str,
    payload: EmailPayload,
    timeout_seconds: int = 45,
    retries: int = 2,
    starttls: bool = True,
    use_ssl: bool = False,
    fallback_ssl: bool = True,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = payload.subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(payload.text_body)
    msg.add_alternative(payload.html_body, subtype="html")

    context = ssl.create_default_context()

    def _send_smtp(port: int, use_ssl_mode: bool, use_starttls: bool) -> None:
        if use_ssl_mode:
            with smtplib.SMTP_SSL(smtp_host, port, timeout=timeout_seconds, context=context) as server:
                server.ehlo()
                if smtp_username:
                    server.login(smtp_username, smtp_password)
                server.send_message(msg)
            return

        with smtplib.SMTP(smtp_host, port, timeout=timeout_seconds) as server:
            server.ehlo()
            if use_starttls:
                server.starttls(context=context)
                server.ehlo()
            if smtp_username:
                server.login(smtp_username, smtp_password)
            server.send_message(msg)

    errors: list[str] = []
    attempts = max(1, retries + 1)
    for attempt in range(attempts):
        try:
            target_port = smtp_port if smtp_port > 0 else (465 if use_ssl else 587)
            _send_smtp(target_port, use_ssl_mode=use_ssl, use_starttls=starttls)
            return
        except (socket.timeout, TimeoutError, ssl.SSLError, smtplib.SMTPException, OSError) as exc:
            errors.append(f"attempt={attempt + 1} primary: {exc}")
            if (not use_ssl) and fallback_ssl:
                try:
                    _send_smtp(465, use_ssl_mode=True, use_starttls=False)
                    return
                except (socket.timeout, TimeoutError, ssl.SSLError, smtplib.SMTPException, OSError) as ssl_exc:
                    errors.append(f"attempt={attempt + 1} fallback_ssl: {ssl_exc}")

            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(
        "SMTP send failed after retries. Last errors: " + " | ".join(errors[-4:])
    )
