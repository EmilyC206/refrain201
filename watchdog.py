"""
Enrichment watchdog — checks for leads with missing company data or failed
enrichment and sends a summary email so you can investigate.

Run after each pipeline pass (or on a cron):
    python watchdog.py

Requires SMTP config in .env (see below).  Does nothing if there are no
problems to report.

.env keys:
    WATCHDOG_SMTP_HOST     (default: smtp.gmail.com)
    WATCHDOG_SMTP_PORT     (default: 587)
    WATCHDOG_SMTP_USER     (your sending email)
    WATCHDOG_SMTP_PASSWORD (app password — never your real password)
    WATCHDOG_NOTIFY_EMAIL  (recipient email for alerts)
"""
from __future__ import annotations

import os
import smtplib
from datetime import date, datetime
from email.mime.text import MIMEText

from dotenv import load_dotenv

from db.schema import ApiUsageLog, LeadRecord, Session, init_db

load_dotenv()

_SMTP_HOST = os.getenv("WATCHDOG_SMTP_HOST", "smtp.gmail.com")
_SMTP_PORT = int(os.getenv("WATCHDOG_SMTP_PORT", "587"))
_SMTP_USER = os.getenv("WATCHDOG_SMTP_USER", "")
_SMTP_PASS = os.getenv("WATCHDOG_SMTP_PASSWORD", "")
_NOTIFY_TO = os.getenv("WATCHDOG_NOTIFY_EMAIL", "")


def _build_report() -> str | None:
    """Returns a plain-text report body, or None if everything looks healthy."""
    sections: list[str] = []

    with Session() as s:
        failed = (
            s.query(LeadRecord)
            .filter(LeadRecord.enrichment_status.in_(["Failed", "hs_pending"]))
            .all()
        )
        if failed:
            lines = [f"  {r.email:40s} status={r.enrichment_status}  error={r.enrichment_error or 'n/a'}" for r in failed]
            sections.append(
                f"== {len(failed)} contact(s) stuck or failed ==\n" + "\n".join(lines)
            )

        no_industry = (
            s.query(LeadRecord)
            .filter_by(enrichment_status="Complete")
            .filter(
                (LeadRecord.industry == None) | (LeadRecord.industry == "")  # noqa: E711
            )
            .all()
        )
        if no_industry:
            lines = [f"  {r.email:40s} domain={r.domain}  company={r.company_name or '?'}" for r in no_industry]
            sections.append(
                f"== {len(no_industry)} enriched contact(s) missing industry ==\n"
                "These domains likely have no Wikidata entry. Consider manual enrichment.\n"
                + "\n".join(lines)
            )

        today = str(date.today())
        usage = s.query(ApiUsageLog).filter_by(date=today).all()
        hot_providers = [u for u in usage if u.cap and u.call_count and u.call_count >= u.cap * 0.8]
        if hot_providers:
            lines = [f"  {u.provider}: {u.call_count}/{u.cap} ({int(u.call_count / u.cap * 100)}%)" for u in hot_providers]
            sections.append(
                "== API usage nearing daily cap ==\n" + "\n".join(lines)
            )

    if not sections:
        return None

    header = f"Enrichment Watchdog Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
    return header + "\n\n".join(sections)


def _send_email(subject: str, body: str) -> None:
    if not all([_SMTP_USER, _SMTP_PASS, _NOTIFY_TO]):
        print("WATCHDOG: SMTP not configured — printing report to stdout instead.\n")
        print(body)
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = _SMTP_USER
    msg["To"] = _NOTIFY_TO

    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
        server.starttls()
        server.login(_SMTP_USER, _SMTP_PASS)
        server.send_message(msg)
    print(f"WATCHDOG: Alert sent to {_NOTIFY_TO}")


def main() -> None:
    init_db()
    report = _build_report()
    if report is None:
        print("WATCHDOG: All clear — nothing to report.")
        return
    _send_email("Enrichment Watchdog Alert", report)


if __name__ == "__main__":
    main()
