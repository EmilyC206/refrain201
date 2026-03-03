# HubSpot Cold Lead Enrichment & Scoring Tool
**A Revenue Operations pipeline that turns a cold email address into a
scored, personalized, and routed HubSpot contact — using only HubSpot's
free tier and open-source intelligence APIs.**

---

## Table of Contents
1. [What This Tool Does & Why It Matters](#1-what-this-tool-does--why-it-matters)
2. [Architecture Overview](#2-architecture-overview)
3. [Project File Structure](#3-project-file-structure)
4. [Database Schema Explained](#4-database-schema-explained)
5. [Scoring Model Explained](#5-scoring-model-explained)
6. [Personalization Hook System Explained](#6-personalization-hook-system-explained)
7. [HubSpot Free Tier Constraints & How We Work Around Them](#7-hubspot-free-tier-constraints--how-we-work-around-them)
8. [Environment Setup — Step by Step](#8-environment-setup--step-by-step)
9. [First-Time HubSpot Property Provisioning](#9-first-time-hubspot-property-provisioning)
10. [Running the Pipeline](#10-running-the-pipeline)
11. [How to Verify It Is Working](#11-how-to-verify-it-is-working)
12. [RevOps Activation Checklist (HubSpot Side)](#12-revops-activation-checklist-hubspot-side)
13. [Common Errors & Fixes](#13-common-errors--fixes)
14. [Rules You Must Never Break](#14-rules-you-must-never-break)

---

## 1. What This Tool Does & Why It Matters

### The RevOps Problem We Are Solving
A cold lead enters HubSpot with only an email address and maybe a name.
Your sales team has no idea:
- Is this person a decision-maker or an intern?
- Is this company even in your target market (ICP)?
- What should the first line of the outreach email say?
- Should an AE own this, or should it go to an SDR nurture sequence?

Answering these questions manually at scale is impossible. Paid enrichment
tools (ZoomInfo, Apollo, Clearbit paid) cost thousands per month.

**This tool solves all four problems for free.**

### What the Tool Does, End to End
```
Cold contact enters HubSpot (just email)
         ↓
Python pipeline picks it up (enrich_status = Pending)
         ↓
OSINT APIs called: domain → company data, email → person data
         ↓
Scoring engine computes 0–100 composite score from 4 dimensions
         ↓
Personalization hook sentence is generated (e.g.,
  "Revenue-focused marketing leaders at Acme are cutting CAC 30% with us.")
         ↓
All data written back to HubSpot via batch API
         ↓
HubSpot workflows and lists route the lead automatically
```

### Revenue Operations Impact
- **Routing:** `lead_score_tier = Hot` contacts go directly to AEs.
- **Prioritization:** SDRs sort their view by `lead_total_score` descending
  — highest fit leads worked first.
- **Personalization:** The `enrich_hook` property injects a company-specific
  sentence into outbound email sequences automatically.
- **Reporting:** After 4 weeks, compare MQL→SQL conversion for enriched vs.
  unenriched contacts. This is your ROI proof to leadership.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        HubSpot Free CRM                          │
│  Contacts ──→ enrich_status = "Pending"                         │
│  Companies ──→ co_icp_fit, co_employee_range, co_tech_stack     │
└──────────────────────────┬──────────────────────────────────────┘
                           │  fetch_pending_contacts() [batch read]
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Python Pipeline (local or cloud)              │
│                                                                  │
│  enrichment/pipeline.py                                          │
│    ├── Wikidata SPARQL  ──→ company: industry, employees, HQ    │
│    ├── hunter.io API    ──→ person: email validity, name        │
│    ├── keyword inference ──→ seniority, job_function            │
│    ├── scoring/engine.py ──→ 0-100 score + Hot/Warm/Cool/Cold  │
│    └── hook builder ──→ personalization sentence                │
│                                                                  │
│  hubspot/sync.py                                                 │
│    └── batch_update_contacts() [batch write, 100 per call]     │
│    └── _check_cap() [guards HubSpot 40k/day limit]             │
└──────────────────────────┬──────────────────────────────────────┘
                           │  writes enrichment back
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Local SQLite Database                        │
│  lead_records      — full enrichment state per contact          │
│  scoring_history   — immutable audit log of score changes       │
│  api_usage_log     — daily call counter per provider            │
└─────────────────────────────────────────────────────────────────┘
```

**Key design principle:** HubSpot is the system of record for sales.
SQLite is the system of record for the pipeline. They stay in sync
but never share a lock. If the pipeline crashes mid-run, no data is lost —
HubSpot contacts still have `enrich_status = Pending` and will be retried.

**Two-phase commit:** The pipeline writes enrichment to SQLite as `hs_pending`
before touching HubSpot. Only after `batch_update_contacts` confirms a
contact was written does SQLite promote it to `Complete` with `hs_synced_at`
stamped. This means a partial or total HubSpot write failure leaves both
sides in a consistent retryable state.

**Quota tracking:** Every external API call consumes a quota slot in
`api_usage_log` before the HTTP request is made — not after. This means
failed requests (timeouts, network errors) still count against the daily cap,
which accurately reflects what the provider's own rate limiter sees.

---

## 3. Project File Structure

```
hubspot_enrichment/
│
├── main.py                      ← Entry point. Run this.
├── requirements.txt             ← All Python dependencies
├── .env.example                 ← Copy to .env and fill in your keys
│
├── db/
│   └── schema.py                ← SQLAlchemy ORM models + init_db()
│
├── enrichment/
│   └── pipeline.py              ← Main orchestration logic
│
├── scoring/
│   └── engine.py                ← Scoring weights, tier thresholds,
│                                   personalization hook templates
│
└── hubspot/
    ├── properties.py            ← Auto-provisions 10 custom properties
    │                               on HubSpot (run once)
    └── sync.py                  ← Read/write HubSpot via batch API
```

---

## 4. Database Schema Explained

File: `db/schema.py`

There are **3 tables**. Understand all three before touching anything.

### Table 1: `lead_records`
**One row per HubSpot contact. This is the heart of the pipeline.**

| Column | Type | Purpose |
|---|---|---|
| `hs_contact_id` | String (PK) | HubSpot's contact ID |
| `email` | String | Contact email address |
| `domain` | String | Extracted from email (e.g., `acme.com`) |
| `job_title` | String | Raw job title from HubSpot |
| `seniority` | String | Inferred ENUM: IC / Manager / Director / VP / CXO |
| `job_function` | String | Inferred ENUM: Marketing / Sales / Engineering / Finance / Operations / Product / Other |
| `company_name` | String | From Wikidata or HubSpot `company` field |
| `industry` | String | From Wikidata (if available) |
| `employee_range` | String | ENUM: 1-10 / 11-50 / 51-200 / 201-1000 / 1001+ |
| `hq_country` | String | From Wikidata (if available) |
| `tech_stack_json` | JSON | Reserved (not populated by default) |
| `score_icp_fit` | Integer | Sub-score 0–40 pts |
| `score_seniority` | Integer | Sub-score 0–25 pts |
| `score_function` | Integer | Sub-score 0–20 pts |
| `score_company_size` | Integer | Sub-score 0–15 pts |
| `total_score` | Integer | Sum of all sub-scores (0–100) |
| `score_tier` | String | Hot / Warm / Cool / Cold |
| `personalization_hook` | Text | Computed one-line outreach sentence |
| `hook_variables_json` | JSON | Inputs used to build the hook |
| `enrichment_status` | String | `Pending` / `hs_pending` / `Complete` / `Failed` / `Stale` |
| `enrichment_source` | String | Which APIs returned data |
| `enrichment_error` | Text | Error message if status = Failed |
| `enriched_at` | DateTime | Timestamp of last enrichment |
| `hs_synced_at` | DateTime | Timestamp of last confirmed HubSpot write-back |

**`enrichment_status` lifecycle:**
```
Pending → hs_pending → Complete
               ↓
             Failed
```
- `Pending` — not yet enriched (or reset for re-enrichment)
- `hs_pending` — enriched and scored locally, HubSpot write not yet confirmed
- `Complete` — enrichment confirmed written to HubSpot (`hs_synced_at` is set)
- `Failed` — pipeline error; see `enrichment_error` for details
- `Stale` — previously enriched but flagged for re-enrichment

The `hs_pending` state is the two-phase commit guard: if the HubSpot batch
write fails after SQLite is written, the contact stays `hs_pending` in SQLite
and `Pending` in HubSpot — both sides agree it needs a retry on the next run.

### Table 2: `scoring_history`
**Immutable. Never update rows here — only insert.**

| Column | Purpose |
|---|---|
| `hs_contact_id` | Which contact changed |
| `old_score` / `new_score` | Before and after |
| `delta` | The difference (can be negative) |
| `old_tier` / `new_tier` | Tier change |
| `trigger_fields` | JSON list of which dimensions changed |
| `changed_at` | Timestamp |

### Table 3: `api_usage_log`
**One row per provider per day.**

| Column | Purpose |
|---|---|
| `date` | YYYY-MM-DD |
| `provider` | hubspot / hunter / wikidata |
| `call_count` | Running total for today |
| `cap` | Maximum allowed calls today |

---

## 5. Scoring Model Explained

File: `scoring/engine.py`

### Score Breakdown (100 points total)

```
ICP Industry Fit:   40 pts   ← Is this company in our target industry?
Seniority:          25 pts   ← Can this person write a check?
Job Function:       20 pts   ← Is this person in a department we sell to?
Company Size:       15 pts   ← Is this company the right size for us?
                   ───────
Total:             100 pts
```

### Tier Thresholds
```
Hot  ≥ 75   → AE-owned. Highest priority. Max 2-day SLA.
Warm 50–74  → SDR-owned. Standard sequence. 7-day SLA.
Cool 25–49  → Nurture track. Low-touch email sequence.
Cold  < 25  → Suppress. Do not actively contact.
```

### How to Tune the Model
1. Open `scoring/engine.py`
2. Adjust the weight dictionaries at the top of the file
3. Adjust `TIER_THRESHOLDS` if too many or too few leads are hitting Hot
4. Re-run the pipeline — existing scores in `scoring_history` are preserved

---

## 6. Personalization Hook System Explained

File: `scoring/engine.py` → `build_personalization_hook()`

Templates are keyed by `(job_function, seniority)`. Variables available:
`{company}`, `{size_desc}`, `{industry}`.

### Adding New Templates
1. Identify a `(job_function, seniority)` pair missing from `HOOK_TEMPLATES`
2. Write a hook sentence for that persona's specific pain point
3. Add it to `HOOK_TEMPLATES` in `engine.py`
4. Do NOT rename `{company}`, `{size_desc}`, `{industry}` — the `.format()` call depends on them exactly

---

## 7. HubSpot Free Tier Constraints & How We Work Around Them

| Constraint | Limit | Our Solution |
|---|---|---|
| Custom properties | 10 total | 7 contact + 3 company. No exceptions. |
| API calls per day | ~40,000 | `_check_cap()` halts at 38,000 |
| API burst rate | 10 req/s | `time.sleep(0.1)` between batches |
| No custom objects | Free tier | Contact + company properties + SQLite |
| Batch update limit | 100 records | `BATCH_SIZE=50` gives headroom |

### The 10 Property Budget — DO NOT EXCEED
```
CONTACTS (7 slots):
  1. enrich_status
  2. enrich_seniority
  3. enrich_function
  4. enrich_hook
  5. lead_total_score
  6. lead_score_tier
  7. enrich_payload_json

COMPANIES (3 slots):
  8. co_employee_range
  9. co_icp_fit
  10. co_tech_stack
```

---

## 8. Environment Setup — Step by Step

### Prerequisites
- Python 3.10+
- A HubSpot Free account
- A HubSpot Private App token (not an API key — deprecated)
- Optional: Hunter.io free account (25 lookups/mo)
- Optional: None for company enrichment — Wikidata SPARQL is used by default (no key)

### Step 1: Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### Step 2: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Create your HubSpot Private App token
1. Go to app.hubspot.com → Settings → Account Setup → Integrations → Private Apps
2. Create app named `Lead Enrichment Pipeline`
3. Enable scopes: `crm.objects.contacts.read/write`, `crm.objects.companies.read/write`,
   `crm.schemas.contacts.read/write`, `crm.schemas.companies.read/write`
4. Copy the token starting with `pat-na1-`

### Step 4: Configure environment variables
```bash
cp .env.example .env
# Edit .env and fill in HUBSPOT_ACCESS_TOKEN
```

### Step 5: Initialize the database
```bash
python -c "from db.schema import init_db; init_db()"
```
Expected output: `DB initialized.`

---

## 9. First-Time HubSpot Property Provisioning

```bash
python main.py --provision
```

Expected output:
```
CREATED: ['contacts.enrich_status', 'contacts.enrich_seniority', ...]
SKIPPED: []
FAILED:  []
```

A `409` response means the property already exists → appears in `SKIPPED`, not `FAILED`.

---

## 10. Running the Pipeline

### One-time run
```bash
python main.py
```

### Scheduled daemon
```bash
python main.py --schedule
```

Runs immediately, then repeats every `ENRICH_INTERVAL_HOURS` hours (default: 4).

### What Happens During a Run
1. `fetch_pending_contacts()` — finds contacts where `enrich_status = Pending` or unset
2. Extract domain from email
3. Query Wikidata SPARQL with the domain → company data (industry, employees, HQ when available)
4. Call Hunter with email → person validation
5. Infer `seniority` and `job_function` from job title
6. `score_lead()` → sub-scores + total + tier
7. `build_personalization_hook()` → 1-line hook
8. Write to `lead_records` in SQLite; append to `scoring_history` if score changed
9. `batch_update_contacts()` → write all back to HubSpot

---

## 11. How to Verify It Is Working

### Check SQLite has records
```bash
python -c "
from db.schema import Session, LeadRecord
with Session() as s:
    count = s.query(LeadRecord).count()
    complete = s.query(LeadRecord).filter_by(enrichment_status='Complete').count()
    print(f'Total: {count}, Complete: {complete}')
"
```

### Check API usage is within limits
```bash
python -c "
from db.schema import Session, ApiUsageLog
from datetime import date
with Session() as s:
    logs = s.query(ApiUsageLog).filter_by(date=str(date.today())).all()
    for l in logs:
        print(f'{l.provider}: {l.call_count}/{l.cap} calls today')
"
```

### Check score distribution
```bash
python -c "
from db.schema import Session, LeadRecord
from sqlalchemy import func
with Session() as s:
    tiers = s.query(LeadRecord.score_tier, func.count()).group_by(LeadRecord.score_tier).all()
    for tier, count in tiers:
        print(f'{tier}: {count} contacts')
"
```

A healthy B2B ICP distribution: Hot 5–15%, Warm 20–35%, Cool 30–40%, Cold 15–30%.
If >50% are Hot, tighten `ICP_INDUSTRIES` weights in `engine.py`.

---

## 12. RevOps Activation Checklist (HubSpot Side)

### Active Lists to Create
- [ ] **Hot Leads — AE Queue**: `lead_score_tier = Hot` AND `enrich_status = Complete`
- [ ] **Warm Leads — SDR Queue**: `lead_score_tier = Warm` AND `enrich_status = Complete`
- [ ] **Nurture Track**: `lead_score_tier = Cool` AND `enrich_status = Complete`
- [ ] **Enrichment Failed**: `enrich_status = Failed`

### Contact View for Sales
Columns: `lead_total_score` (sort desc), `lead_score_tier`, `enrich_seniority`, `enrich_function`, `enrich_hook`

### Email Personalization Token
```
{{ contact.enrich_hook }}
```

---

## 13. Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Token invalid or expired | Re-generate Private App token |
| `403 Forbidden` on provision | Missing `crm.schemas.contacts.write` scope | Edit Private App, add scope |
| `Daily cap reached` | Hit 38,000 HubSpot calls | Increase `BATCH_SIZE` or lower enrichment frequency |
| Wikidata returns no results | Domain not present as an official website in Wikidata | Normal — pipeline uses fallbacks and continues |
| `SQLite database is locked` | Two pipeline instances running | Kill all, run as single process |
| All scores are 0 | Job title empty in HubSpot | Ensure `jobtitle` is populated before enrichment |
| `enrich_hook` blank | Missing `(function, seniority)` pair | Add template to `HOOK_TEMPLATES` in `engine.py` |
| Contacts stuck as `hs_pending` | HubSpot write kept failing | Check `WARN batch` lines in logs; verify token scopes and cap usage |
| `WARN batch N failed` in logs | Transient HubSpot error on one batch | Pipeline continues with other batches; affected contacts retry next run |

---

## 14. Rules You Must Never Break

1. **Never exceed 10 custom HubSpot properties.** Upgrade to Starter first.
2. **Never call a HubSpot API endpoint without `_check_cap()` first.**
3. **Never use the v1 or v2 HubSpot APIs.** Use v3 only.
4. **Never delete rows from `scoring_history`.** It is an audit log.
5. **Never change a property `name` after creation.** It is immutable in HubSpot.
6. **Always use batch endpoints.** 100 contacts = 1 API call.
7. **Always mark failures** in `lead_records.enrichment_status = "Failed"`.

---

## Enrichment Watchdog (Email Alerts)

`watchdog.py` scans SQLite after each pipeline run and emails you a report
if any of these conditions are true:

- Contacts stuck in `Failed` or `hs_pending` status
- Enriched contacts missing industry data (Wikidata had no match for the domain)
- Any API provider at 80%+ of its daily cap

### Setup
Add these to `.env`:
```
WATCHDOG_SMTP_HOST=smtp.gmail.com
WATCHDOG_SMTP_PORT=587
WATCHDOG_SMTP_USER=you@gmail.com
WATCHDOG_SMTP_PASSWORD=your-app-password
WATCHDOG_NOTIFY_EMAIL=alerts@yourcompany.com
```

### Run
```bash
python watchdog.py
```

If SMTP is not configured, the report prints to stdout instead. Run it after
each pipeline pass or on its own cron schedule.

---

## Quick Reference: Key Files & Their Single Responsibility

| File | One Job |
|---|---|
| `main.py` | Entry point. Args: `--provision`, `--schedule`, or bare run |
| `watchdog.py` | Post-run alert script. Emails you when enrichment has issues. |
| `db/schema.py` | Defines the 3 SQLite tables. Call `init_db()` once at startup |
| `hubspot/properties.py` | Provisions HubSpot custom properties via API. Run once. |
| `hubspot/sync.py` | Reads from and writes to HubSpot. Enforces rate limits. |
| `enrichment/pipeline.py` | Orchestrates: fetch → enrich → score → hook → write |
| `scoring/engine.py` | Pure functions: `score_lead()` and `build_personalization_hook()` |
| `.env` | All secrets and config. Never commit this file. |

---

*Built for HubSpot Free CRM. Python 3.10+. No paid enrichment tools required.*
*Uses Wikidata SPARQL for company enrichment (no API key). Hunter.io optional.*
*Maintained by RevOps Engineering.*
