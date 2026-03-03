from __future__ import annotations

import argparse
import os
import time

from dotenv import load_dotenv

load_dotenv()


def _provision() -> None:
    from hubspot.properties import provision_properties
    provision_properties()


def _run_once() -> None:
    from enrichment.pipeline import run_pipeline
    run_pipeline()


def main() -> None:
    from db.schema import init_db
    init_db()

    parser = argparse.ArgumentParser(
        description="HubSpot Cold Lead Enrichment & Scoring Pipeline",
    )
    parser.add_argument(
        "--provision",
        action="store_true",
        help="Create HubSpot custom properties (run once per portal).",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run continuously on ENRICH_INTERVAL_HOURS schedule.",
    )
    args = parser.parse_args()

    if args.provision:
        _provision()
        return

    interval_minutes = int(os.getenv("ENRICH_INTERVAL_MINUTES", "0"))
    interval_hours = int(os.getenv("ENRICH_INTERVAL_HOURS", "4"))
    interval_seconds = interval_minutes * 60 if interval_minutes else interval_hours * 3600

    if args.schedule:
        if interval_minutes:
            print(f"Scheduled mode — running every {interval_minutes} minute(s). Ctrl+C to stop.")
        else:
            print(f"Scheduled mode — running every {interval_hours} hour(s). Ctrl+C to stop.")
        while True:
            _run_once()
            if interval_minutes:
                print(f"Sleeping {interval_minutes}m until next run…")
            else:
                print(f"Sleeping {interval_hours}h until next run…")
            time.sleep(interval_seconds)
    else:
        _run_once()


if __name__ == "__main__":
    main()
