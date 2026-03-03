from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

from db.schema import LeadRecord, ScoringHistory, Session
from hubspot.sync import _check_cap, _increment_usage, batch_update_contacts, fetch_pending_contacts
from scoring.engine import SIZE_DESCRIPTIONS, build_personalization_hook, infer_job_function, infer_seniority, score_lead

load_dotenv()

_CLEARBIT_KEY = os.getenv("CLEARBIT_API_KEY", "")
_HUNTER_KEY   = os.getenv("HUNTER_API_KEY", "")
_HTTP_TIMEOUT = 15


def _extract_domain(email: str) -> str:
    return email.split("@")[-1].lower().strip() if "@" in email else ""


def _fetch_clearbit(domain: str) -> dict[str, Any]:
    """Calls Clearbit Company API. Returns {} if key unset or call fails."""
    if not _CLEARBIT_KEY or not domain:
        return {}
    _check_cap("clearbit", cost=1)
    try:
        r = httpx.get(
            "https://company.clearbit.com/v1/companies/find",
            params={"domain": domain},
            headers={"Authorization": f"Bearer {_CLEARBIT_KEY}"},
            timeout=_HTTP_TIMEOUT,
        )
        _increment_usage("clearbit", cost=1)
        if r.status_code == 200:
            return r.json()
        return {}
    except Exception:
        return {}


def _fetch_hunter(email: str) -> dict[str, Any]:
    """Calls Hunter email verifier. Returns {} if key unset or call fails."""
    if not _HUNTER_KEY or not email:
        return {}
    _check_cap("hunter", cost=1)
    try:
        r = httpx.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": _HUNTER_KEY},
            timeout=_HTTP_TIMEOUT,
        )
        _increment_usage("hunter", cost=1)
        if r.status_code == 200:
            return r.json().get("data", {})
        return {}
    except Exception:
        return {}


def _map_employee_count(count: int | None) -> str | None:
    if count is None:
        return None
    if count <= 10:
        return "1-10"
    if count <= 50:
        return "11-50"
    if count <= 200:
        return "51-200"
    if count <= 1000:
        return "201-1000"
    return "1001+"


def _enrich_one(contact: dict) -> dict | None:
    """
    Enriches a single HubSpot contact dict.
    Returns a flat enrichment dict ready to upsert, or None if no email.
    """
    props  = contact.get("properties", {})
    email  = (props.get("email") or "").strip()
    hs_id  = contact.get("id", "")

    if not email:
        return None

    domain       = _extract_domain(email)
    job_title    = props.get("jobtitle") or ""
    company_name = props.get("company") or ""

    clearbit = _fetch_clearbit(domain)
    hunter   = _fetch_hunter(email)

    # Clearbit-derived fields
    industry       = (clearbit.get("category") or {}).get("industry") or None
    employee_cnt   = (clearbit.get("metrics") or {}).get("employees")
    employee_range = _map_employee_count(employee_cnt)
    hq_country     = (clearbit.get("geo") or {}).get("country") or None
    tech_stack     = [t.get("name") for t in (clearbit.get("tech") or [])[:8] if t.get("name")]
    if not company_name:
        company_name = clearbit.get("name") or ""

    # Hunter can supplement the company name when Clearbit is unavailable
    if not company_name and hunter:
        company_name = hunter.get("company") or ""

    seniority    = infer_seniority(job_title)
    job_function = infer_job_function(job_title)

    scores = score_lead(
        industry=industry,
        seniority=seniority,
        job_function=job_function,
        employee_range=employee_range,
    )

    size_desc = SIZE_DESCRIPTIONS.get(employee_range or "", "")
    hook, hook_vars = build_personalization_hook(
        company_name=company_name,
        size_desc=size_desc,
        industry=industry,
        job_function=job_function,
        seniority=seniority,
    )

    sources = [name for name, data in [("clearbit", clearbit), ("hunter", hunter)] if data]

    return {
        "hs_contact_id":      hs_id,
        "email":              email,
        "domain":             domain,
        "job_title":          job_title,
        "seniority":          seniority,
        "job_function":       job_function,
        "company_name":       company_name,
        "industry":           industry,
        "employee_range":     employee_range,
        "hq_country":         hq_country,
        "tech_stack_json":    tech_stack or None,
        **scores,
        "personalization_hook": hook,
        "hook_variables_json":  hook_vars or None,
        "enrichment_status":  "Complete",
        "enrichment_source":  "+".join(sources) if sources else "none",
        "enriched_at":        datetime.utcnow(),
    }


def _upsert_lead(session, data: dict) -> tuple[int | None, str | None]:
    """Upserts a LeadRecord. Returns (old_score, old_tier) for change detection."""
    existing  = session.get(LeadRecord, data["hs_contact_id"])
    old_score = existing.total_score if existing else None
    old_tier  = existing.score_tier  if existing else None

    if existing is None:
        session.add(LeadRecord(**data))
    else:
        for k, v in data.items():
            setattr(existing, k, v)

    return old_score, old_tier


def _maybe_log_score_change(
    session,
    data: dict,
    old_score: int | None,
    old_tier: str | None,
) -> None:
    """Appends to scoring_history only when score or tier actually changed."""
    new_score = data["total_score"]
    new_tier  = data["score_tier"]
    if old_score == new_score and old_tier == new_tier:
        return
    session.add(
        ScoringHistory(
            hs_contact_id=data["hs_contact_id"],
            old_score=old_score,
            new_score=new_score,
            delta=(new_score - old_score) if old_score is not None else new_score,
            old_tier=old_tier,
            new_tier=new_tier,
            trigger_fields=["industry", "seniority", "job_function", "employee_range"],
        )
    )


def run_pipeline() -> dict:
    """
    Full pipeline: fetch pending contacts → enrich → score → write SQLite → write HubSpot.
    Returns a summary dict with processed / complete / failed / skipped counts.
    """
    print("Fetching pending contacts from HubSpot…")
    contacts = fetch_pending_contacts()
    print(f"  Found {len(contacts)} contact(s) to process.")

    hs_updates: list[dict] = []
    stats = {"processed": 0, "complete": 0, "failed": 0, "skipped": 0}

    for contact in contacts:
        hs_id = contact.get("id", "unknown")
        try:
            enriched = _enrich_one(contact)
            if enriched is None:
                print(f"  SKIP {hs_id} — no email")
                stats["skipped"] += 1
                continue

            with Session() as session:
                old_score, old_tier = _upsert_lead(session, enriched)
                _maybe_log_score_change(session, enriched, old_score, old_tier)
                session.commit()

            hs_updates.append({
                "id": hs_id,
                "properties": {
                    "enrich_status":       "Complete",
                    "enrich_seniority":    enriched["seniority"],
                    "enrich_function":     enriched["job_function"],
                    "enrich_hook":         enriched["personalization_hook"],
                    "lead_total_score":    str(enriched["total_score"]),
                    "lead_score_tier":     enriched["score_tier"],
                    "enrich_payload_json": str(enriched.get("tech_stack_json") or ""),
                },
            })
            stats["complete"] += 1
            print(
                f"  OK   {hs_id} | {enriched['email']} | "
                f"score={enriched['total_score']} tier={enriched['score_tier']}"
            )

        except RuntimeError as cap_err:
            # Daily cap hit — abort the run cleanly, don't mark contacts as failed
            print(f"  CAP  {hs_id}: {cap_err}")
            break

        except Exception as exc:
            print(f"  FAIL {hs_id}: {exc}")
            stats["failed"] += 1
            props = contact.get("properties", {})
            email = (props.get("email") or "").strip()
            with Session() as session:
                existing = session.get(LeadRecord, hs_id)
                if existing:
                    existing.enrichment_status = "Failed"
                    existing.enrichment_error  = str(exc)
                else:
                    session.add(LeadRecord(
                        hs_contact_id=hs_id,
                        email=email,
                        domain=_extract_domain(email),
                        enrichment_status="Failed",
                        enrichment_error=str(exc),
                    ))
                session.commit()

        finally:
            stats["processed"] += 1

    print(f"Writing {len(hs_updates)} update(s) to HubSpot…")
    batch_update_contacts(hs_updates)
    print(f"Run complete: {stats}")
    return stats
