# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

HubSpot Cold Lead Enrichment & Scoring Tool — a single-service Python pipeline. See `README.md` for full architecture and setup docs.

### Services

| Service | How to run | Notes |
|---|---|---|
| Pipeline (one-shot) | `source venv/bin/activate && python main.py` | Fetches pending HubSpot contacts, enriches, scores, writes back. Requires `HUBSPOT_ACCESS_TOKEN` in `.env`. |
| Pipeline (scheduled) | `source venv/bin/activate && python main.py --schedule` | Runs every `ENRICH_INTERVAL_HOURS` (default 4). |
| HubSpot property provisioning | `source venv/bin/activate && python main.py --provision` | Run once per HubSpot portal to create custom properties. |
| Watchdog | `source venv/bin/activate && python watchdog.py` | Post-run health check; prints to stdout if SMTP not configured. |

### Lint / test / build

- **Lint:** `source venv/bin/activate && ruff check .` (ruff is installed in the venv)
- **Tests:** No automated test suite exists in this repo.
- **Build:** No build step; the pipeline runs directly via `python main.py`.

### Non-obvious caveats

- The `pyproject.toml` describes a `src/coldlead/` CLI layout that **does not exist on disk**. The actual runnable code uses `main.py` at the repo root with `requirements.txt` dependencies. Ignore `pyproject.toml` for running the application.
- The `.env` file must have a valid `HUBSPOT_ACCESS_TOKEN` for the pipeline to fetch/write contacts. Without it, the pipeline will run but find 0 contacts (the HubSpot search API returns empty results for an unauthenticated request).
- SQLite database is created automatically by `init_db()` (called at pipeline startup). The path is configured via `DB_PATH` in `.env`.
- The scoring engine (`scoring/engine.py`) and hook builder are pure functions that can be tested independently without any API keys.
