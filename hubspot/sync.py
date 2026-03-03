from __future__ import annotations

import os
import time
from datetime import date
from typing import Any

import httpx
from dotenv import load_dotenv

from db.schema import ApiUsageLog, Session

load_dotenv()

_TOKEN      = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
_BASE       = "https://api.hubapi.com"
_HEADERS    = {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}
_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
_HS_CAP     = int(os.getenv("DAILY_HS_CALL_CAP", "38000"))

# Per-provider daily call caps (HubSpot free tier + free API tiers)
_PROVIDER_CAPS: dict[str, int] = {
    "hubspot":  _HS_CAP,
    "hunter":   25,
    "clearbit": 500,
}


def _get_or_create_usage(session, provider: str) -> ApiUsageLog:
    today = str(date.today())
    row = session.query(ApiUsageLog).filter_by(date=today, provider=provider).first()
    if row is None:
        row = ApiUsageLog(
            date=today,
            provider=provider,
            call_count=0,
            cap=_PROVIDER_CAPS.get(provider, 9999),
        )
        session.add(row)
        session.flush()
    return row


def _check_cap(provider: str, cost: int = 1) -> None:
    """
    Raises RuntimeError if today's usage + cost would exceed the daily cap.
    Must be called before EVERY external API call — no exceptions.
    """
    with Session() as session:
        row = _get_or_create_usage(session, provider)
        if (row.call_count or 0) + cost > row.cap:
            raise RuntimeError(
                f"Daily cap reached for {provider}: "
                f"{row.call_count}/{row.cap} calls used today."
            )
        session.commit()


def _increment_usage(provider: str, cost: int = 1) -> None:
    """Increments the recorded call count for provider after a successful call."""
    with Session() as session:
        row = _get_or_create_usage(session, provider)
        row.call_count = (row.call_count or 0) + cost
        session.commit()


def fetch_pending_contacts(limit: int = 100) -> list[dict[str, Any]]:
    """
    Returns up to `limit` HubSpot contacts where enrich_status = Pending
    OR the property has never been set.  Uses v3 search endpoint.
    Costs 1 HubSpot API call.
    """
    _check_cap("hubspot", cost=1)

    payload = {
        "filterGroups": [
            {
                "filters": [
                    {"propertyName": "enrich_status", "operator": "EQ", "value": "Pending"}
                ]
            },
            {
                "filters": [
                    {"propertyName": "enrich_status", "operator": "NOT_HAS_PROPERTY"}
                ]
            },
        ],
        "properties": ["email", "firstname", "lastname", "jobtitle", "company"],
        "limit": min(limit, 100),
    }

    r = httpx.post(
        f"{_BASE}/crm/v3/objects/contacts/search",
        headers=_HEADERS,
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    _increment_usage("hubspot", cost=1)
    return r.json().get("results", [])


def batch_update_contacts(updates: list[dict[str, Any]]) -> list[str]:
    """
    Writes enrichment properties back to HubSpot in batches of BATCH_SIZE.
    Each batch = 1 API call.  Sleeps 0.1 s between batches for rate limiting.

    Each item in `updates` must be:
        {"id": "<hs_contact_id>", "properties": {"key": "value", ...}}

    Returns the list of contact IDs that were successfully written.
    Failed batches are logged and skipped — a single bad batch does not
    abort subsequent ones, and callers can use the returned IDs to determine
    which SQLite records to mark as fully synced.
    """
    if not updates:
        return []

    synced_ids: list[str] = []

    for i in range(0, len(updates), _BATCH_SIZE):
        chunk = updates[i : i + _BATCH_SIZE]
        try:
            _check_cap("hubspot", cost=1)
            _increment_usage("hubspot", cost=1)
            r = httpx.post(
                f"{_BASE}/crm/v3/objects/contacts/batch/update",
                headers=_HEADERS,
                json={"inputs": chunk},
                timeout=30,
            )
            r.raise_for_status()
            synced_ids.extend(item["id"] for item in chunk)
        except RuntimeError:
            # Cap exceeded — stop immediately, don't attempt further batches
            raise
        except Exception as exc:
            print(f"  WARN batch {i // _BATCH_SIZE + 1} failed ({len(chunk)} contacts): {exc}")

        # Respect HubSpot's 10 req/s burst limit
        time.sleep(0.1)

    return synced_ids
