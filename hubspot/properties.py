from __future__ import annotations

import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
_BASE = "https://api.hubapi.com"
_HEADERS = {
    "Authorization": f"Bearer {_TOKEN}",
    "Content-Type": "application/json",
}

# 7 contact properties + 3 company properties = exactly 10 custom properties.
# DO NOT add more without upgrading to HubSpot Starter first.
_CONTACT_PROPERTIES: list[dict] = [
    {
        "name": "enrich_status",
        "label": "Enrichment Status",
        "type": "enumeration",
        "fieldType": "select",
        "options": [
            {"label": "Pending",  "value": "Pending",  "displayOrder": 0},
            {"label": "Complete", "value": "Complete", "displayOrder": 1},
            {"label": "Failed",   "value": "Failed",   "displayOrder": 2},
            {"label": "Stale",    "value": "Stale",    "displayOrder": 3},
        ],
        "groupName": "contactinformation",
    },
    {
        "name": "enrich_seniority",
        "label": "Enrichment Seniority",
        "type": "string",
        "fieldType": "text",
        "groupName": "contactinformation",
    },
    {
        "name": "enrich_function",
        "label": "Enrichment Job Function",
        "type": "string",
        "fieldType": "text",
        "groupName": "contactinformation",
    },
    {
        "name": "enrich_hook",
        "label": "Personalization Hook",
        "type": "string",
        "fieldType": "textarea",
        "groupName": "contactinformation",
    },
    {
        "name": "lead_total_score",
        "label": "Lead Total Score",
        "type": "number",
        "fieldType": "number",
        "groupName": "contactinformation",
    },
    {
        "name": "lead_score_tier",
        "label": "Lead Score Tier",
        "type": "enumeration",
        "fieldType": "select",
        "options": [
            {"label": "Hot",  "value": "Hot",  "displayOrder": 0},
            {"label": "Warm", "value": "Warm", "displayOrder": 1},
            {"label": "Cool", "value": "Cool", "displayOrder": 2},
            {"label": "Cold", "value": "Cold", "displayOrder": 3},
        ],
        "groupName": "contactinformation",
    },
    {
        "name": "enrich_payload_json",
        "label": "Enrichment Payload (JSON)",
        "type": "string",
        "fieldType": "textarea",
        "groupName": "contactinformation",
    },
]

_COMPANY_PROPERTIES: list[dict] = [
    {
        "name": "co_employee_range",
        "label": "Employee Range",
        "type": "enumeration",
        "fieldType": "select",
        "options": [
            {"label": "1-10",     "value": "1-10",     "displayOrder": 0},
            {"label": "11-50",    "value": "11-50",    "displayOrder": 1},
            {"label": "51-200",   "value": "51-200",   "displayOrder": 2},
            {"label": "201-1000", "value": "201-1000", "displayOrder": 3},
            {"label": "1001+",    "value": "1001+",    "displayOrder": 4},
        ],
        "groupName": "companyinformation",
    },
    {
        "name": "co_icp_fit",
        "label": "ICP Fit Industry",
        "type": "string",
        "fieldType": "text",
        "groupName": "companyinformation",
    },
    {
        "name": "co_tech_stack",
        "label": "Tech Stack",
        "type": "string",
        "fieldType": "textarea",
        "groupName": "companyinformation",
    },
]


def _create_property(object_type: str, payload: dict) -> str:
    """POSTs one property definition. Returns 'created', 'skipped', or 'failed'."""
    url = f"{_BASE}/crm/v3/properties/{object_type}"
    try:
        r = httpx.post(url, headers=_HEADERS, json=payload, timeout=15)
        if r.status_code == 201:
            return "created"
        if r.status_code == 409:
            # Property already exists — safe to ignore
            return "skipped"
        print(f"  WARN {object_type}.{payload['name']}: {r.status_code} {r.text[:200]}")
        return "failed"
    except Exception as exc:
        print(f"  ERROR {object_type}.{payload['name']}: {exc}")
        return "failed"


def provision_properties() -> dict[str, list[str]]:
    """
    Creates all 10 custom HubSpot properties.
    Safe to call repeatedly — 409 responses are treated as SKIPPED, not FAILED.
    """
    results: dict[str, list[str]] = {"CREATED": [], "SKIPPED": [], "FAILED": []}

    for prop in _CONTACT_PROPERTIES:
        outcome = _create_property("contacts", prop)
        results[outcome.upper()].append(f"contacts.{prop['name']}")
        time.sleep(0.12)

    for prop in _COMPANY_PROPERTIES:
        outcome = _create_property("companies", prop)
        results[outcome.upper()].append(f"companies.{prop['name']}")
        time.sleep(0.12)

    print(f"CREATED: {results['CREATED']}")
    print(f"SKIPPED: {results['SKIPPED']}")
    print(f"FAILED:  {results['FAILED']}")
    return results
