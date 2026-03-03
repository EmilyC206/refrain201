from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

from db.schema import LeadRecord, ScoringHistory, Session
from hubspot.sync import _check_cap, _increment_usage, batch_update_companies, batch_update_contacts, fetch_pending_contacts
from scoring.engine import SIZE_DESCRIPTIONS, build_personalization_hook, infer_job_function, infer_seniority, score_lead

load_dotenv()

_CLEARBIT_KEY = os.getenv("CLEARBIT_API_KEY", "")
_HUNTER_KEY   = os.getenv("HUNTER_API_KEY", "")
_HTTP_TIMEOUT = 15


def _get_associated_company_id(contact: dict) -> str | None:
    """Extracts the first associated company ID from a contact search result."""
    assoc = contact.get("associations", {})
    companies = assoc.get("companies", {}).get("results", [])
    if companies:
        return str(companies[0].get("id", ""))
    return None


def _extract_domain(email: str) -> str:
    return email.split("@")[-1].lower().strip() if "@" in email else ""


# Domain-based fallback intelligence for targets where OSINT APIs return nothing.
# Maps domain suffixes and exact domains to (industry, employee_range, hq_country).
_DOMAIN_INTEL: dict[str, tuple[str, str, str]] = {
    # Federal TLDs
    ".gov":  ("Federal Government / Defense", "1001+", "US"),
    ".mil":  ("Federal Government / Defense", "1001+", "US"),
    # Contracting primes
    "bah.com":               ("System Integration / Federal IT", "1001+", "US"),
    "leidos.com":            ("System Integration / Federal IT", "1001+", "US"),
    "caci.com":              ("System Integration / Federal IT", "1001+", "US"),
    "gdit.com":              ("System Integration / Federal IT", "1001+", "US"),
    "saic.com":              ("System Integration / Federal IT", "1001+", "US"),
    "mantech.com":           ("System Integration / Federal IT", "1001+", "US"),
    "peraton.com":           ("System Integration / Federal IT", "1001+", "US"),
    "parsons.com":           ("System Integration / Federal IT", "1001+", "US"),
    "accenturefederal.com":  ("System Integration / Federal IT", "1001+", "US"),
    "deloitte.com":          ("System Integration / Federal IT", "1001+", "US"),
    "cgifederal.com":        ("System Integration / Federal IT", "201-1000", "US"),
    "northropgrumman.com":   ("System Integration / Federal IT", "1001+", "US"),
    # MSSPs and cyber vendors
    "optiv.com":             ("Managed Security Services", "1001+", "US"),
    "guidepoint.com":        ("Managed Security Services", "201-1000", "US"),
    "coalfire.com":          ("Managed Security Services", "201-1000", "US"),
    "telos.com":             ("Managed Security Services", "201-1000", "US"),
    "presidio.com":          ("Managed Security Services", "201-1000", "US"),
    "arcticwolf.com":        ("Managed Security Services", "1001+", "US"),
    "secureworks.com":       ("Managed Security Services", "1001+", "US"),
    "crowdstrike.com":       ("Cybersecurity", "1001+", "US"),
    "paloaltonetworks.com":  ("Cybersecurity", "1001+", "US"),
    # FFRDCs
    "noblis.org":            ("System Integration / Federal IT", "201-1000", "US"),
    "mitre.org":             ("System Integration / Federal IT", "1001+", "US"),
    # GSA distributors
    "carahsoft.com":         ("Technology", "201-1000", "US"),
    "cdwg.com":              ("Technology", "1001+", "US"),
    "immersionnet.com":      ("Technology", "51-200", "US"),
    "unisonind.com":         ("Technology", "51-200", "US"),
    "fourinc.com":           ("Technology", "51-200", "US"),
}


def _lookup_domain_intel(domain: str) -> tuple[str | None, str | None, str | None]:
    """Falls back to known domain intelligence when OSINT APIs return nothing."""
    if domain in _DOMAIN_INTEL:
        return _DOMAIN_INTEL[domain]
    for suffix, intel in _DOMAIN_INTEL.items():
        if suffix.startswith(".") and domain.endswith(suffix):
            return intel
    return None, None, None


def _fetch_clearbit(domain: str) -> dict[str, Any]:
    """Calls Clearbit Company API. Returns {} if key unset or call fails."""
    if not _CLEARBIT_KEY or not domain:
        return {}
    _check_cap("clearbit", cost=1)
    _increment_usage("clearbit", cost=1)  # record before the call — a failed request still consumed a slot
    try:
        r = httpx.get(
            "https://company.clearbit.com/v1/companies/find",
            params={"domain": domain},
            headers={"Authorization": f"Bearer {_CLEARBIT_KEY}"},
            timeout=_HTTP_TIMEOUT,
        )
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
    _increment_usage("hunter", cost=1)  # record before the call — a failed request still consumed a slot
    try:
        r = httpx.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": _HUNTER_KEY},
            timeout=_HTTP_TIMEOUT,
        )
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

    # Domain-based fallback for .gov/.mil and known primes/MSSPs
    if not industry or not employee_range:
        fb_industry, fb_range, fb_country = _lookup_domain_intel(domain)
        if not industry and fb_industry:
            industry = fb_industry
        if not employee_range and fb_range:
            employee_range = fb_range
        if not hq_country and fb_country:
            hq_country = fb_country

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
    fb_used = _lookup_domain_intel(domain)[0] is not None and not clearbit
    if fb_used:
        sources.append("domain-intel")

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

    hs_contact_updates: list[dict] = []
    hs_company_updates: list[dict] = []
    stats = {"processed": 0, "complete": 0, "failed": 0, "skipped": 0}

    for contact in contacts:
        hs_id = contact.get("id", "unknown")
        try:
            enriched = _enrich_one(contact)
            if enriched is None:
                print(f"  SKIP {hs_id} — no email")
                stats["skipped"] += 1
                continue

            # Write to SQLite as "hs_pending" — not "Complete" until HubSpot
            # confirms receipt. This prevents contacts getting stuck if the
            # HubSpot write fails: they stay hs_pending in SQLite, and
            # HubSpot still shows them as Pending, so the next run retries.
            sqlite_data = {**enriched, "enrichment_status": "hs_pending"}
            with Session() as session:
                old_score, old_tier = _upsert_lead(session, sqlite_data)
                _maybe_log_score_change(session, enriched, old_score, old_tier)
                session.commit()

            payload_summary = json.dumps({
                "company": enriched.get("company_name") or "",
                "industry": enriched.get("industry") or "",
                "employees": enriched.get("employee_range") or "",
                "country": enriched.get("hq_country") or "",
                "source": enriched.get("enrichment_source") or "none",
                "scores": {
                    "icp": enriched["score_icp_fit"],
                    "seniority": enriched["score_seniority"],
                    "function": enriched["score_function"],
                    "size": enriched["score_company_size"],
                },
            }, separators=(",", ":"))

            hs_contact_updates.append({
                "id": hs_id,
                "properties": {
                    "enrich_status":       "Complete",
                    "enrich_seniority":    enriched["seniority"],
                    "enrich_function":     enriched["job_function"],
                    "enrich_hook":         enriched["personalization_hook"],
                    "lead_total_score":    str(enriched["total_score"]),
                    "lead_score_tier":     enriched["score_tier"],
                    "enrich_payload_json": payload_summary,
                },
            })

            company_id = _get_associated_company_id(contact)
            if company_id:
                co_props: dict[str, str] = {}
                if enriched.get("industry"):
                    co_props["co_icp_fit"] = enriched["industry"]
                if enriched.get("employee_range"):
                    co_props["co_employee_range"] = enriched["employee_range"]
                if enriched.get("tech_stack_json"):
                    co_props["co_tech_stack"] = str(enriched["tech_stack_json"])
                if co_props:
                    hs_company_updates.append({
                        "id": company_id,
                        "properties": co_props,
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

    print(f"Writing {len(hs_contact_updates)} contact update(s) to HubSpot…")
    synced_ids = batch_update_contacts(hs_contact_updates)

    # Promote only confirmed-synced contacts from hs_pending → Complete
    if synced_ids:
        now = datetime.utcnow()
        with Session() as session:
            for hs_id in synced_ids:
                record = session.get(LeadRecord, hs_id)
                if record:
                    record.enrichment_status = "Complete"
                    record.hs_synced_at = now
            session.commit()

    unsynced = len(hs_contact_updates) - len(synced_ids)
    if unsynced:
        print(f"  WARN {unsynced} contact(s) remain hs_pending — will retry on next run")

    if hs_company_updates:
        print(f"Writing {len(hs_company_updates)} company update(s) to HubSpot…")
        co_synced = batch_update_companies(hs_company_updates)
        co_failed = len(set(u["id"] for u in hs_company_updates)) - len(co_synced)
        if co_failed:
            print(f"  WARN {co_failed} company update(s) failed — will retry on next run")
        else:
            print(f"  OK   {len(co_synced)} company(ies) updated")

    stats["complete"] = len(synced_ids)
    print(f"Run complete: {stats}")
    return stats
