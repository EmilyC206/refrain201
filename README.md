# HubSpot Cold Lead Enrichment & Scoring Tool
**A Revenue Operations pipeline that turns a cold email address into a
scored, personalized, and routed HubSpot contact.

---

## Table of Contents
1. [What This Tool Does & Why It Matters](#1-what-this-tool-does--why-it-matters)
2. [Architecture Overview](#2-architecture-overview)
3. [Project File Structure](#3-project-file-structure)
4. [Database Schema Explained](#4-database-schema-explained)
5. [Scoring Model Explained](#5-scoring-model-explained)
6. [Personalization Hook System Explained](#6-personalization-hook-system-explained)

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
│                    Python Pipeline (local or cloud)             │
│                                                                 │
│  enrichment/pipeline.py                                         │
│    ├── Wikidata SPARQL  ──→ company: industry, employees, HQ    │
│    ├── hunter.io API    ──→ person: email validity, name        │
│    ├── keyword inference ──→ seniority, job_function            │
│    ├── scoring/engine.py ──→ 0-100 score + Hot/Warm/Cool/Cold   │
│    └── hook builder ──→ personalization sentence                │
│                                                                 │
│  hubspot/sync.py                                                │
│    └── batch_update_contacts() [batch write, 100 per call]      │
│    └── _check_cap() [guards HubSpot 40k/day limit]              │
└──────────────────────────┬──────────────────────────────────────┘
                           │  writes enrichment back
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Local SQLite Database                       │
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
ICP Industry Fit:   40 pts   ← Is this company in our target industry? What segmentation ahve we targeted?
Seniority:          25 pts   ← Can this person write a check? (Are they a shot-caller)
Job Function:       20 pts   ← Is this person in a department we sell to or have they reached out for a demo prior?
Company Size:       15 pts   ← Is this company the right size for us? What is their revenue?
                   ───────
Total:             100 pts
```

### Tier Thresholds
```
Hot  ≥ 75   → AE-owned. Highest priority. Max 2-day SLA. Sp
Warm 50–74  → BDR-owned. Standard sequence. 7-day SLA with personalization angle built in.
Cool 25–49  → Nurture track. Low-touch email sequence that increases scoring based off how far they get in Flare_Academy.
Cold  < 25  → Suppress. Do not actively contact. We have actively disqualifed via Trial refusal.
```

### How to Tune the Model
1. Open `scoring/engine.py`
2. Adjust the weight dictionaries at the top of the file
3. Adjust `TIER_THRESHOLDS` if too many or too few leads are hitting Hot
4. Re-run the pipeline — existing scores in `scoring_history` are preserved

---

## 6. Personalization Hook System Explained

File: `scoring/engine.py` → `build_personalization_hook()`

Templates are keyed by `(job_function, seniority)`. Variables we are querying: Lead status, prior_contact, job_function, level of enrichment

### Adding New Templates
1. Identify a `(job_function, seniority)` pair missing from `HOOK_TEMPLATES`
2. Write a hook sentence for that persona's specific pain point
3. Add it to `HOOK_TEMPLATES` to be called via HUBSPOT API
#The hook templates are going to be focused on ABM marketing's direction. See JR call notes, and what we can do to tweak as API will require different seat / api permissions than demo version.
5. Do NOT rename `{company}`, `{size_desc}`, `{industry}` — the `.format()` call depends on them exactly


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
