"""
One-time seed loader: reads flare_federal_targets.csv and upserts each
contact into HubSpot with enrich_status = Pending so the enrichment
pipeline picks them up on its next scheduled run.

Usage:
    python targets/seed_hubspot.py                          # default CSV path
    python targets/seed_hubspot.py --csv path/to/file.csv   # custom CSV
    python targets/seed_hubspot.py --dry-run                # preview without API calls
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hubspot.sync import _check_cap, _increment_usage  # noqa: E402

load_dotenv()

_TOKEN   = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
_BASE    = "https://api.hubapi.com"
_HEADERS = {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}

_DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "flare_federal_targets.csv")


def _upsert_contact(row: dict, dry_run: bool = False) -> str:
    """
    Creates or updates a HubSpot contact by email.
    Returns 'created', 'exists', or 'failed'.
    """
    email = (row.get("email") or "").strip()
    if not email:
        return "failed"

    props = {
        "email": email,
        "firstname": row.get("firstname", ""),
        "lastname": row.get("lastname", ""),
        "jobtitle": row.get("jobtitle", ""),
        "company": row.get("company", ""),
        "enrich_status": "Pending",
    }

    if dry_run:
        print(f"  DRY  {email} | {props['company']} | {props['jobtitle']}")
        return "created"

    _check_cap("hubspot", cost=1)
    _increment_usage("hubspot", cost=1)

    try:
        r = httpx.post(
            f"{_BASE}/crm/v3/objects/contacts",
            headers=_HEADERS,
            json={"properties": props},
            timeout=15,
        )
        if r.status_code == 201:
            return "created"
        if r.status_code == 409:
            return "exists"
        print(f"  WARN {email}: {r.status_code} {r.text[:200]}")
        return "failed"
    except RuntimeError:
        raise
    except Exception as exc:
        print(f"  ERROR {email}: {exc}")
        return "failed"


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed HubSpot with Flare federal targets")
    parser.add_argument("--csv", default=_DEFAULT_CSV, help="Path to targets CSV")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making API calls")
    args = parser.parse_args()

    with open(args.csv, newline="") as f:
        rows = list(csv.DictReader(f))

    print(f"Loaded {len(rows)} target(s) from {args.csv}")
    if args.dry_run:
        print("DRY RUN — no HubSpot API calls will be made\n")

    stats = {"created": 0, "exists": 0, "failed": 0}

    for row in rows:
        result = _upsert_contact(row, dry_run=args.dry_run)
        stats[result] += 1
        if result == "created" and not args.dry_run:
            print(f"  OK   {row['email']} | {row['company']}")
        elif result == "exists":
            print(f"  SKIP {row['email']} (already in HubSpot)")
        time.sleep(0.1)

    print(f"\nSeed complete: {stats}")


if __name__ == "__main__":
    main()
