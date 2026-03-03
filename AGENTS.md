# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is **ColdLead** — a Python CLI pipeline that enriches and scores HubSpot cold leads using OSINT APIs (Clearbit, Hunter.io). See `README.md` for full architecture and scoring model details.

### Running the application

```bash
source venv/bin/activate
python main.py            # one-shot pipeline run
python main.py --schedule # continuous scheduled mode
python main.py --provision # one-time HubSpot property setup
```

### Key environment variables

The code reads `HUBSPOT_ACCESS_TOKEN` (in `hubspot/sync.py`) and `DB_PATH` (in `db/schema.py`). The `.env.example` file uses different names (`HUBSPOT_PRIVATE_APP_TOKEN`, `COLDLEAD_DB_PATH`) — make sure the `.env` includes both `HUBSPOT_ACCESS_TOKEN` and `DB_PATH` for the pipeline to work. Copy `.env.example` to `.env` and add those keys if missing.

### Database

SQLite database is auto-created by `init_db()` (called at the start of `main.py`). The DB path is controlled by the `DB_PATH` env var. No separate DB server needed.

### Testing

There are no automated tests in this repository. To verify the scoring engine works, import and call functions from `scoring/engine.py` directly:

```python
from scoring.engine import score_lead, infer_seniority, infer_job_function
scores = score_lead(industry="SaaS", seniority="VP", job_function="Marketing", employee_range="201-1000")
```

### Linting

No linting tools are configured in this repository. You may run `python -m py_compile <file>` to check syntax.

### External API dependencies

- **HubSpot API** (required): Set `HUBSPOT_ACCESS_TOKEN` env var. Without it, the pipeline cannot fetch or update contacts.
- **Clearbit** (optional): Set `CLEARBIT_API_KEY` for company enrichment. Pipeline gracefully degrades without it.
- **Hunter.io** (optional): Set `HUNTER_API_KEY` for email verification. Pipeline gracefully degrades without it.

### Gotchas

- The `pyproject.toml` declares a separate `coldlead` package with `typer` CLI under `src/`, but that code does not exist yet. The actual runnable code uses `main.py` with `argparse` and `requirements.txt`.
- `python3.12-venv` system package is needed to create the virtual environment on Ubuntu.
