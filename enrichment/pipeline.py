from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from urllib.parse import urlparse

from db.schema import LeadRecord, ScoringHistory, Session
from hubspot.sync import _check_cap, _increment_usage, batch_update_companies, batch_update_contacts, fetch_pending_contacts
from scoring.engine import SIZE_DESCRIPTIONS, build_personalization_hook, infer_job_function, infer_seniority, score_lead

load_dotenv()

_HUNTER_KEY   = os.getenv("HUNTER_API_KEY", "")
_WIKIDATA_ENDPOINT = os.getenv("WIKIDATA_ENDPOINT", "https://query.wikidata.org/sparql")
_WIKIDATA_UA = os.getenv(
    "WIKIDATA_USER_AGENT",
    "refrain201/0.1 (Wikidata SPARQL client; contact: you@example.com)",
)
_WIKIDATA_TIMEOUT_S = float(os.getenv("WIKIDATA_TIMEOUT_S", "30"))
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


def _fetch_wikidata(domain: str, company_hint: str | None = None) -> dict[str, Any]:
    """
    Calls Wikidata SPARQL to enrich company facts from an email domain.
    Returns a dict with keys: name, industry, employees, country (when available).
    """
    if not domain:
        return {}

    domain_l = domain.lower().replace('"', "")
    hint_l = (company_hint or "").strip().lower().replace('"', "")

    # Anchor to the host, otherwise domains like "notgoogle.com/?ref=google.com" can match.
    # Allow subdomains: ([a-z0-9-]+\\.)*example\\.com
    domain_regex = domain_l.replace(".", "\\\\.")
    hint_clause = ""
    if hint_l:
        hint_clause = f"""
  ?item rdfs:label ?label .
  FILTER(LANG(?label) = "en")
  FILTER(CONTAINS(LCASE(STR(?label)), "{hint_l}"))
""".rstrip()

    def _run_query(*, host_regex: str | None, require_website: bool) -> list[dict]:
        website_line = "?item wdt:P856 ?website ." if require_website else "OPTIONAL { ?item wdt:P856 ?website . }"
        host_filter = f'FILTER(REGEX(LCASE(STR(?website)), "{host_regex}"))' if host_regex else ""
        query = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?item ?itemLabel ?website ?industryItemLabel ?employees ?countryItemLabel
WHERE {{
  VALUES ?type {{ wd:Q43229 wd:Q4830453 wd:Q783794 wd:Q6881511 }}
  ?item wdt:P31 ?type .
  {website_line}
  {host_filter}
{hint_clause}
  OPTIONAL {{ ?item wdt:P452 ?industryItem . }}
  OPTIONAL {{ ?item wdt:P1128 ?employees . }}
  OPTIONAL {{ ?item wdt:P17 ?countryItem . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 50
""".strip()

        try:
            _check_cap("wikidata", cost=1)
            _increment_usage("wikidata", cost=1)  # record before the call — a failed request still consumed a slot
            r = httpx.get(
                _WIKIDATA_ENDPOINT,
                params={"format": "json", "query": query},
                headers={"Accept": "application/sparql+json", "User-Agent": _WIKIDATA_UA},
                timeout=httpx.Timeout(_WIKIDATA_TIMEOUT_S),
            )
            if r.status_code != 200:
                return []
            data = r.json()
            return (((data or {}).get("results") or {}).get("bindings") or [])
        except Exception:
            return []

    try:
        # Prefer the root domain (or www.) match to avoid subdomain noise.
        root_regex = f"^(https?://)?(www\\\\.)?{domain_regex}(/|$)"
        sub_regex  = f"^(https?://)?([a-z0-9-]+\\\\.)*{domain_regex}(/|$)"

        bindings = _run_query(host_regex=root_regex, require_website=True)
        if not bindings:
            bindings = _run_query(host_regex=sub_regex, require_website=True)
        if not bindings and hint_l:
            # Fallback: domain may not match the org's official website (e.g. google.com → about.google).
            # Try a hint-only lookup and rank candidates by website similarity.
            bindings = _run_query(host_regex=None, require_website=False)
        if not bindings:
            return {}
        def _v(row: dict, key: str) -> str | None:
            return (row.get(key) or {}).get("value")

        by_item: dict[str, dict[str, Any]] = {}

        for row in bindings:
            item_uri = _v(row, "item")
            if not item_uri:
                continue

            entry = by_item.setdefault(
                item_uri,
                {
                    "name": _v(row, "itemLabel"),
                    "industry": None,
                    "country": None,
                    "employees": None,
                    "websites": [],
                },
            )

            w = _v(row, "website")
            if w:
                entry["websites"].append(w)

            if not entry["industry"]:
                entry["industry"] = _v(row, "industryItemLabel")
            if not entry["country"]:
                entry["country"] = _v(row, "countryItemLabel")

            emp_raw = _v(row, "employees")
            if emp_raw:
                try:
                    emp = int(float(emp_raw))
                    entry["employees"] = emp if entry["employees"] is None else max(entry["employees"], emp)
                except Exception:
                    pass

        def _score(candidate: dict[str, Any]) -> int:
            label = (candidate.get("name") or "").lower()
            score = 0
            brand = domain_l.split(".")[0]

            if hint_l:
                if label == hint_l:
                    score += 100
                elif label.startswith(hint_l):
                    score += 60
                elif hint_l in label:
                    score += 30

            # Penalize obvious community/group pages that often sit on subdomains.
            if any(bad in label for bad in ("developer", "developers", "group", "community", "user group", "gdg")):
                score -= 40
            if any(bad in label for bad in ("affiliate", "network", "forum", "club")):
                score -= 20

            # Prefer \"more official\" entities (they tend to have these fields populated).
            if candidate.get("employees") is not None:
                score += 20
            if candidate.get("industry"):
                score += 5
            if candidate.get("country"):
                score += 5

            # Prefer shorter names when all else is equal (\"Google\" > \"Google X Y Z\").
            words = [w for w in label.split() if w]
            if len(words) > 1:
                score -= 3 * (len(words) - 1)

            for website in candidate.get("websites") or []:
                host = (urlparse(website).hostname or "").lower()
                if host in {domain_l, f"www.{domain_l}"}:
                    score += 30
                elif host.endswith(f".{domain_l}"):
                    score += 10
                if brand and (host.endswith(f".{brand}") or brand in host):
                    score += 5

            return score

        best = max(by_item.values(), key=_score, default=None)
        if not best:
            return {}

        name = best.get("name") or ""
        if name.startswith("Q") and name[1:].isdigit():
            name = ""

        return {
            "name": name or None,
            "industry": best.get("industry"),
            "employees": best.get("employees"),
            "country": best.get("country"),
        }
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

    wikidata = _fetch_wikidata(domain, company_hint=company_name)
    hunter   = _fetch_hunter(email)

    industry       = wikidata.get("industry") or None
    employee_cnt   = wikidata.get("employees")
    employee_range = _map_employee_count(employee_cnt) if isinstance(employee_cnt, int) else None
    hq_country     = wikidata.get("country") or None
    tech_stack     = None
    if not company_name:
        company_name = wikidata.get("name") or ""

    # Hunter can supplement the company name when Wikidata has no match
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

    sources = [name for name, data in [("wikidata", wikidata), ("hunter", hunter)] if data]

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
