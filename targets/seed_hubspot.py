"""
One-time script: reads flare_federal_seed.csv and creates HubSpot contacts
for each target row. Each contact gets:
  - email      : target_title_slug@domain  (unique placeholder)
  - jobtitle   : target_title from CSV
  - company    : company_name from CSV
  - enrich_status = Pending  (pipeline will enrich on next run)

Run from the project root:
    python3 targets/seed_hubspot.py
"""
from __future__ import annotations

import csv
import os
import re
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
_BASE  = "https://api.hubapi.com"
_HDR   = {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}
_CSV   = os.path.join(os.path.dirname(__file__), "flare_federal_seed.csv")


def _slug(text: str) -> str:
    """Turns a job title into a safe email local-part."""
    text = text.lower().split("/")[0].strip()          # take first title only
    text = re.sub(r"[^a-z0-9]+", ".", text)            # non-alphanum → dot
    text = re.sub(r"\.{2,}", ".", text).strip(".")     # collapse/trim dots
    return text[:40]                                   # keep it short


def create_contact(row: dict) -> tuple[bool, str]:
    domain    = row["domain"].strip().lstrip("www.").lower()
    slug      = _slug(row["target_title"])
    email     = f"{slug}@{domain}"
    company   = row["company_name"].strip()
    title     = row["target_title"].strip()
    segment   = row["segment"].strip()
    sam       = row["sam_pattern"].strip()

    payload = {
        "properties": {
            "email":          email,
            "jobtitle":       title,
            "company":        company,
            "enrich_status":  "Pending",
            # Store segment and SAM pattern in the notes field for context
            "hs_lead_status": "NEW",
        }
    }

    r = httpx.post(f"{_BASE}/crm/v3/objects/contacts", headers=_HDR, json=payload, timeout=15)

    if r.status_code == 201:
        return True, email
    if r.status_code == 409:
        return True, f"{email} (already exists)"
    return False, f"{email} → {r.status_code} {r.text[:120]}"


def main() -> None:
    if not _TOKEN:
        print("ERROR: HUBSPOT_ACCESS_TOKEN not set in .env")
        return

    with open(_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Seeding {len(rows)} contacts into HubSpot…\n")
    ok = fail = skip = 0

    for i, row in enumerate(rows, 1):
        success, msg = create_contact(row)
        status = "OK  " if success else "FAIL"
        print(f"  [{i:02d}] {status} {msg}")
        if success:
            ok += 1
        else:
            fail += 1
        time.sleep(0.12)   # stay well under HubSpot's 10 req/s burst limit

    print(f"\nDone — {ok} created/existing, {fail} failed.")
    print("Run  python3 main.py  to start the enrichment and scoring pass.")


if __name__ == "__main__":
    main()
