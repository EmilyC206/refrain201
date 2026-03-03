from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from urllib.parse import urlparse

from db.schema import LeadRecord, ScoringHistory, Session
from hubspot.sync import _check_cap, _increment_usage, batch_update_contacts, fetch_pending_contacts
from scoring.engine import SIZE_DESCRIPTIONS, build_personalization_hook, infer_job_function, infer_seniority, score_lead

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Domain → industry override map.
# Wikidata returns no usable industry label for .gov/.mil domains and many
# federal contractor domains.  This map is checked before Wikidata so the ICP
# score reflects the actual sector, not the "Other" fallback.
# ──────────────────────────────────────────────────────────────────────────────
_DOMAIN_INDUSTRY_OVERRIDES: dict[str, str] = {
    # ── Federal civilian agencies ──────────────────────────────────────────
    "tsp.gov":              "Federal Government",
    "ssa.gov":              "Federal Government",
    "va.gov":               "Federal Government",
    "irs.gov":              "Federal Government",
    "treasury.gov":         "Federal Government",
    "opm.gov":              "Federal Government",
    "dol.gov":              "Federal Government",
    "cms.hhs.gov":          "Federal Government",
    "hhs.gov":              "Federal Government",
    "sba.gov":              "Federal Government",
    "ed.gov":               "Federal Government",
    "gsa.gov":              "Federal Government",
    "state.gov":            "Federal Government",
    "doi.gov":              "Federal Government",
    "usda.gov":             "Federal Government",
    "dot.gov":              "Federal Government",
    "epa.gov":              "Federal Government",
    # ── Financial regulators & sector guardians ────────────────────────────
    "cisa.dhs.gov":         "Federal Government",
    "dhs.gov":              "Federal Government",
    "fincen.gov":           "Federal Government",
    "sec.gov":              "Financial Regulation",
    "occ.treas.gov":        "Financial Regulation",
    "fdic.gov":             "Financial Regulation",
    "federalreserve.gov":   "Financial Regulation",
    "cfpb.gov":             "Financial Regulation",
    "cftc.gov":             "Financial Regulation",
    "ncua.gov":             "Financial Regulation",
    # ── Law enforcement ────────────────────────────────────────────────────
    "fbi.gov":              "Law Enforcement",
    "dea.gov":              "Law Enforcement",
    "atf.gov":              "Law Enforcement",
    "secretservice.gov":    "Law Enforcement",
    "ice.gov":              "Law Enforcement",
    "justice.gov":          "Law Enforcement",
    "usmarshals.gov":       "Law Enforcement",
    "postalinspectors.uspis.gov": "Law Enforcement",
    "uspis.gov":            "Law Enforcement",
    "cbp.gov":              "Law Enforcement",
    # ── Defense & intelligence ─────────────────────────────────────────────
    "nsa.gov":              "Intelligence",
    "cia.gov":              "Intelligence",
    "dia.mil":              "Intelligence",
    "disa.mil":             "Defense",
    "cybercom.mil":         "Defense",
    "dodcio.defense.gov":   "Defense",
    "defense.gov":          "Defense",
    "16af.af.mil":          "Defense",
    "arcyber.army.mil":     "Defense",
    "af.mil":               "Defense",
    "army.mil":             "Defense",
    "navy.mil":             "Defense",
    "marines.mil":          "Defense",
    "spaceforce.mil":       "Defense",
    "socom.mil":            "Defense",
    # ── Systems integrators / primes ──────────────────────────────────────
    "boozallen.com":        "Systems Integration",
    "saic.com":             "Systems Integration",
    "leidos.com":           "Systems Integration",
    "mitre.org":            "Systems Integration",
    "mantech.com":          "Systems Integration",
    "caci.com":             "Systems Integration",
    "gdit.com":             "Systems Integration",
    "peraton.com":          "Systems Integration",
    "parsons.com":          "Systems Integration",
    "unisongt.com":         "Systems Integration",
    "northropgrumman.com":  "Defense",
    "l3harris.com":         "Defense",
    "raytheon.com":         "Defense",
    "lm.com":               "Defense",
    "lockheedmartin.com":   "Defense",
    "bah.com":              "Systems Integration",
    "accenturefederal.com": "Systems Integration",
    "accenture.com":        "Systems Integration",
    "deloitte.com":         "Systems Integration",
    "ibm.com":              "Systems Integration",
    "noblis.org":           "Systems Integration",
    "immersionnet.com":     "Systems Integration",
    # ── Federal MSSPs ──────────────────────────────────────────────────────
    "mandiant.com":         "Managed Security",
    "crowdstrike.com":      "Managed Security",
    "paloaltonetworks.com": "Managed Security",
    "secureworks.com":      "Managed Security",
    "telos.com":            "Managed Security",
    "arcticwolf.com":       "Managed Security",
    "coalfire.com":         "Managed Security",
    "optiv.com":            "Managed Security",
    "silversky.com":        "Managed Security",
    "guidepoint.com":       "Managed Security",
    "presidio.com":         "Managed Security",
    "cdwg.com":             "Systems Integration",
    "carahsoft.com":        "Systems Integration",
}

# Employee-count overrides for domains where Wikidata returns nothing.
# Values are raw employee counts; _map_employee_count() converts them.
_DOMAIN_EMPLOYEE_OVERRIDES: dict[str, int] = {
    # Federal agencies — treat as large enterprise
    "tsp.gov": 500, "ssa.gov": 60000, "va.gov": 400000, "irs.gov": 80000,
    "treasury.gov": 100000, "opm.gov": 5000, "dol.gov": 15000,
    "cms.hhs.gov": 6000, "sba.gov": 3000, "ed.gov": 4000,
    "cisa.dhs.gov": 3000, "dhs.gov": 240000, "fincen.gov": 350,
    "sec.gov": 4500, "occ.treas.gov": 3500, "fdic.gov": 5800,
    "federalreserve.gov": 20000, "cfpb.gov": 1700,
    "fbi.gov": 35000, "dea.gov": 10000, "atf.gov": 5000,
    "secretservice.gov": 6500, "ice.gov": 20000, "justice.gov": 115000,
    "usmarshals.gov": 5400, "nsa.gov": 30000, "disa.mil": 8000,
    "cybercom.mil": 2000, "dia.mil": 16500,
    # Primes and MSSPs
    "boozallen.com": 29000, "saic.com": 24000, "leidos.com": 47000,
    "mitre.org": 10000, "mantech.com": 9000, "caci.com": 22000,
    "gdit.com": 30000, "peraton.com": 14000, "northropgrumman.com": 95000,
    "l3harris.com": 50000, "accenture.com": 700000, "deloitte.com": 330000,
    "ibm.com": 280000, "mandiant.com": 2000, "crowdstrike.com": 8000,
    "paloaltonetworks.com": 14000, "secureworks.com": 2500, "telos.com": 2000,
    "arcticwolf.com": 2000, "coalfire.com": 1200, "optiv.com": 2000,
}

_HUNTER_KEY   = os.getenv("HUNTER_API_KEY", "")
_WIKIDATA_ENDPOINT = os.getenv("WIKIDATA_ENDPOINT", "https://query.wikidata.org/sparql")
_WIKIDATA_UA = os.getenv(
    "WIKIDATA_USER_AGENT",
    "refrain201/0.1 (Wikidata SPARQL client; contact: you@example.com)",
)
_WIKIDATA_TIMEOUT_S = float(os.getenv("WIKIDATA_TIMEOUT_S", "30"))
_HTTP_TIMEOUT = 15


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

    # Domain overrides take precedence over Wikidata when available.
    # Match on full domain first, then try stripping one subdomain level.
    _domain_key = domain
    if _domain_key not in _DOMAIN_INDUSTRY_OVERRIDES:
        _parent = ".".join(domain.split(".")[-2:]) if domain.count(".") >= 2 else domain
        _domain_key = _parent if _parent in _DOMAIN_INDUSTRY_OVERRIDES else domain

    industry       = _DOMAIN_INDUSTRY_OVERRIDES.get(_domain_key) or wikidata.get("industry") or None
    _emp_override  = _DOMAIN_EMPLOYEE_OVERRIDES.get(_domain_key)
    employee_cnt   = _emp_override if _emp_override is not None else wikidata.get("employees")
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

            # Write to SQLite as "hs_pending" — not "Complete" until HubSpot
            # confirms receipt. This prevents contacts getting stuck if the
            # HubSpot write fails: they stay hs_pending in SQLite, and
            # HubSpot still shows them as Pending, so the next run retries.
            sqlite_data = {**enriched, "enrichment_status": "hs_pending"}
            with Session() as session:
                old_score, old_tier = _upsert_lead(session, sqlite_data)
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
    synced_ids = batch_update_contacts(hs_updates)

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

    unsynced = len(hs_updates) - len(synced_ids)
    if unsynced:
        print(f"  WARN {unsynced} contact(s) remain hs_pending — will retry on next run")

    stats["complete"] = len(synced_ids)
    print(f"Run complete: {stats}")
    return stats
