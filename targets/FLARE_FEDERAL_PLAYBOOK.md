# Flare Federal HubSpot Enrichment Playbook

**How to run a federal cybersecurity go-to-market motion on HubSpot's free tier using automated lead enrichment, scoring, and personalized outreach.**

---

## The Problem This Solves

You have a federal targeting list. Names, agencies, titles. But HubSpot free gives you zero intelligence about who to call first, what to say, or which contacts are worth your time.

This pipeline turns a raw email address into a scored, personalized, routed contact — automatically, every 5 minutes, at zero marginal cost.

---

## How It Works (30-Second Version)

```
CSV of federal targets
    ↓  seed_hubspot.py (one-time load)
HubSpot contacts with enrich_status = "Pending"
    ↓  main.py --schedule (runs every 5 min)
Pipeline: OSINT APIs → score (0-100) → tier (Hot/Warm/Cool/Cold) → hook sentence
    ↓  batch write back to HubSpot
7 enriched contact properties + 3 company properties
    ↓  HubSpot active lists + contact views
Reps see a prioritized queue with personalized first lines
```

---

## Your 10 Custom Properties (Free Tier Budget)

HubSpot free allows exactly 10 custom properties. Every one is allocated:

### Contact Properties (7)

| Property | What It Holds | How Sales Uses It |
|---|---|---|
| `enrich_status` | Pending / Complete / Failed / Stale | Filter to find un-enriched contacts |
| `enrich_seniority` | CXO / VP / Director / Manager / IC | Sort by decision-making authority |
| `enrich_function` | Security / Threat Intelligence / Procurement / etc. | Identify champion persona |
| `lead_total_score` | 0–100 composite score | Sort contacts by priority |
| `lead_score_tier` | Hot / Warm / Cool / Cold | Route to right owner + sequence |
| `enrich_hook` | One-line personalized outreach sentence | Copy-paste into first email |
| `enrich_payload_json` | Compact JSON with company, industry, scores, source | Quick-reference enrichment data |

### Company Properties (3)

| Property | What It Holds | How Sales Uses It |
|---|---|---|
| `co_icp_fit` | Industry classification | Filter companies by vertical |
| `co_employee_range` | 1-10 / 11-50 / 51-200 / 201-1000 / 1001+ | Filter by org size |
| `co_tech_stack` | Detected technologies | Identify integration opportunities |

---

## Scoring Model: How Contacts Get Ranked

Every contact scores 0–100 across four dimensions tuned for Flare's federal ICP:

### ICP Industry Fit (40 points max)

| Industry | Points | Why |
|---|---|---|
| Federal Government / Defense | 40 | Direct end-buyer |
| Law Enforcement | 40 | Dark web investigation buyer |
| Cybersecurity | 38 | Core market adjacency |
| Managed Security Services | 35 | Channel / embedding partner |
| System Integration / Federal IT | 30 | Prime contractor teaming |
| Financial Services | 22 | Sector risk guardian |
| Technology | 15 | General tech adjacency |

### Seniority (25 points max)

| Level | Points | Mapping |
|---|---|---|
| CXO | 25 | CISO, CTO, Chief, President |
| VP | 22 | VP, Vice President |
| Director | 18 | Director, Section Chief, SAC |
| Manager | 10 | Program Manager, Lead, Contracting Officer |
| IC | 4 | Analyst, Specialist |

### Job Function (20 points max)

| Function | Points | Flare's Champion Persona |
|---|---|---|
| Security | 20 | CISO and security operations — the buyer |
| Threat Intelligence | 20 | CTI teams — the daily user |
| IT / Engineering | 18 | Integration into SIEM/SOAR stack |
| Operations | 15 | SOC/ops workflows |
| Procurement / Contracting | 12 | Federal purchasing authority |
| Marketing / Sales | 10 | Prime BD and proposal teams |

### Company Size (15 points max)

| Size | Points | Federal Context |
|---|---|---|
| 1001+ | 15 | Cabinet agencies, large primes |
| 201-1000 | 13 | Mid-tier primes, large MSSPs |
| 51-200 | 8 | Niche integrators, FFRDCs |
| 11-50 | 4 | Small primes |
| 1-10 | 1 | Boutique consultancies |

### Tier Thresholds

| Tier | Score Range | What It Means | Action |
|---|---|---|---|
| **Hot** | 75-100 | Federal CISO at a large agency. Call today. | Direct outreach, 2-day SLA |
| **Warm** | 50-74 | Right persona, weaker ICP fit or seniority. | Email sequence, 7-day SLA |
| **Cool** | 25-49 | Partial match — monitor for signals. | Nurture track, low-touch |
| **Cold** | 0-24 | Poor fit. Don't waste cycles. | Suppress |

### Score Examples

| Contact | ICP | Seniority | Function | Size | **Total** | **Tier** |
|---|---|---|---|---|---|---|
| CISO, CISA (DHS) | 40 | 25 | 20 | 15 | **100** | Hot |
| Director CTI, State Dept | 40 | 18 | 20 | 15 | **93** | Hot |
| VP Cyber, Booz Allen | 30 | 22 | 20 | 15 | **87** | Hot |
| Contracting Officer, DHS | 40 | 10 | 12 | 15 | **77** | Hot |
| VP Cyber Practice, Carahsoft | 15 | 22 | 20 | 13 | **70** | Warm |
| Director Vendor Alliances, CDW-G | 15 | 18 | 3 | 13 | **49** | Cool |

---

## Targeting Tiers → HubSpot Lists

The 5-tier targeting strategy maps directly to HubSpot active lists:

### List 1: "Hot — Federal End Buyers" (Tier 1A/B/C/D from targeting doc)

**Filter:** `lead_score_tier = Hot` AND `enrich_status = Complete`

These are CISOs, CTI directors, and section chiefs at federal agencies with active SAM.gov solicitations or proven dark-web budgets. This is your direct sales list.

**Personas in this list:**
- CISA, FinCEN, FBI, USSS, VA, OPM, SSA, CMS, State Dept — end buyers
- CYBERCOM, DIA, NSA, AFRL, DISA — DoD CTI platform buyers
- FDA OCI, HHS OIG, USPIS — law enforcement investigation buyers

**Outreach:** Personal, high-touch. Use `enrich_hook` as opening line. Reference specific SAM.gov solicitations where applicable.

### List 2: "Hot — Prime & MSSP Partners" (Tier 2 + 3)

**Filter:** `lead_score_tier = Hot` AND `enrich_function IN [Sales, Marketing, Security]` AND company matches prime/MSSP names

These are the Booz Allen cyber VPs, CACI intelligence directors, and Optiv federal practice leads who can embed Flare into their managed services or proposals.

**Outreach:** Partnership pitch. Use `enrich_hook` templates that reference proposals, recompetes, and subcontract differentiation.

### List 3: "Warm — Nurture Pipeline"

**Filter:** `lead_score_tier = Warm` AND `enrich_status = Complete`

Contacts with the right function but weaker industry or seniority fit. Future opportunities when budget cycles or org changes create openings.

**Outreach:** Quarterly email with relevant Flare case study. Invite to webinar or event. Monitor for re-enrichment triggers.

### List 4: "Enrichment Failed"

**Filter:** `enrich_status = Failed`

Contacts the pipeline couldn't enrich. Review manually — could be a data quality issue or a .mil/.gov domain that OSINT APIs can't reach.

---

## The Personalization Hook System

Every enriched contact gets a one-line outreach sentence generated from their persona. This is stored in `enrich_hook` and available as `{{ contact.enrich_hook }}` in HubSpot email templates.

### How Templates Work

Templates are keyed by `(job_function, seniority)`:

| Persona | Hook |
|---|---|
| Security + CXO | "CISOs at {company} are using Flare to surface credential leaks and dark-web threats before adversaries act." |
| Threat Intelligence + Director | "Threat intel directors at {company} are detecting credential exposures and brand abuse in hours, not weeks." |
| Procurement + Manager | "Contracting officers at {industry} agencies are evaluating Flare's dark-web platform for existing cyber task orders." |
| Sales + VP (for primes) | "VP Sales at {size_desc} {industry} primes are embedding Flare into proposals to win cyber task orders." |

30 templates covering every function × seniority combination relevant to federal cyber.

**Usage:** In your HubSpot outbound sequence, set the first line as:

```
{{ contact.enrich_hook }}
```

Every email opens with a persona-specific, company-specific line — no manual research required.

---

## Step-by-Step Setup

### 1. Provision HubSpot properties (run once)

```bash
python main.py --provision
```

Creates all 10 custom properties. Safe to re-run — existing properties are skipped.

### 2. Load federal targeting list

```bash
# Preview first
python targets/seed_hubspot.py --dry-run

# Load for real
python targets/seed_hubspot.py
```

Creates contacts in HubSpot with `enrich_status = Pending`.

### 3. Run the enrichment pipeline

```bash
# One-time run
python main.py

# Or continuous (every 5 minutes)
ENRICH_INTERVAL_MINUTES=5 python main.py --schedule
```

Pipeline fetches Pending contacts, enriches, scores, writes back.

### 4. Build active lists in HubSpot

Create these lists manually in HubSpot (Settings → Lists):

| List Name | Filter |
|---|---|
| Hot Leads — Direct Outreach | `lead_score_tier = Hot` AND `enrich_status = Complete` |
| Warm Leads — Nurture | `lead_score_tier = Warm` AND `enrich_status = Complete` |
| Enrichment Failed | `enrich_status = Failed` |
| All Enriched | `enrich_status = Complete` |

### 5. Create the sales contact view

In HubSpot, create a saved view with these columns (sorted by `lead_total_score` descending):

1. Name
2. Company
3. `lead_total_score` (sort desc)
4. `lead_score_tier`
5. `enrich_seniority`
6. `enrich_function`
7. `enrich_hook`

This gives reps a prioritized work queue where the highest-value contacts are always on top.

### 6. Wire hooks into email sequences

Create a HubSpot email template. First line:

```
{{ contact.enrich_hook }}
```

Body: Standard Flare value prop for the contact's tier.

---

## Contracting Vehicles Strategy (Tier 4 — Non-Contact)

Tier 4 targets aren't people — they're procurement paths. Track these as HubSpot deals or notes:

| Vehicle | Timeline | Action |
|---|---|---|
| GSA MAS (SIN 54151HACS) | 0-6 months | Apply for listing |
| NASA SEWP VI | 0-6 months | Partner with Four Inc. or Optiv+ClearShark |
| CISA CDM APL | 6-12 months | Submit monthly during open windows |
| DHS Alliant 3 / CIO-SP4 | 6-12 months | Position as sub on prime task orders |
| Army ITES-SW2 | 6-12 months | Direct or partner listing |
| CISA SCS Recompete | 12-24 months | Position for next cycle |
| DoD ESI | 12-24 months | Pursue listing alongside ZeroFox |

---

## Competitive Displacement Strategy (Tier 5 — Intelligence)

Use the `enrich_payload_json` field and HubSpot notes to track competitive context per account:

| Incumbent | Where They Are | Flare's Angle |
|---|---|---|
| ZeroFox | CISA SCS, GSA, DoD ESI, CDM | Deeper dark web: 50K Telegram channels, 92% stealer log ecosystem, data to 2017 |
| Recorded Future | USCYBERCOM | Dark web depth vs. their breadth. Complementary specialist positioning |
| DarkOwl | SEWP V, ITES-SW2 via Four Inc. | Integrated CTEM platform vs. data-only. Better analyst UX |
| Mandiant | CISA SCS, Accenture Federal | Complementary — Flare adds dark web specialty to their IR/TI stack |
| SpyCloud | AFRL SBIR pipeline | Broader than identity-only. Full CTEM coverage |
| Dataminr | DISA (30 seats) | Different coverage — surface web vs. Flare's dark web |

When engaging a target account, check if an incumbent is already embedded. Position Flare as:
- **Replacement** (ZeroFox, DarkOwl) — deeper coverage, better value
- **Complement** (Recorded Future, Mandiant, Dataminr) — adds dark web layer they don't have

---

## Operational Cadence

| Frequency | Action |
|---|---|
| Every 5 minutes | Pipeline auto-enriches new Pending contacts |
| Daily | Review Hot leads list — ensure outreach within 2-day SLA |
| Weekly | Review Warm leads — batch nurture sequence |
| Weekly | Check "Enrichment Failed" list — manually fix or re-queue |
| Monthly | Review score distribution — tune weights if >50% are Hot or <5% |
| Quarterly | Re-enrich Stale contacts (set `enrich_status = Stale` to trigger) |
| Per campaign | Load new CSV via `seed_hubspot.py` — pipeline auto-enriches |

---

## Adding New Targets

To add more contacts at any time:

1. Create a CSV with columns: `email`, `firstname`, `lastname`, `jobtitle`, `company`, `tier_reason`
2. Run: `python targets/seed_hubspot.py --csv path/to/new_targets.csv`
3. Pipeline picks them up on next scheduled run

The system is designed to scale. Load 10 contacts or 10,000 — the pipeline handles batching, rate limiting, and quota tracking automatically.

---

## Free Tier Constraints & Workarounds

| Constraint | Limit | How We Handle It |
|---|---|---|
| Custom properties | 10 total | Exactly 10 allocated (7 contact + 3 company). No room for more. |
| API calls/day | ~40,000 | `_check_cap()` halts at 38,000. Pipeline self-limits. |
| API burst rate | 10 req/s | 0.1s sleep between batches |
| Active lists | 5 on free | Use the 4 lists above + 1 spare |
| Workflows | Limited on free | Use active lists for routing instead of workflows |
| Sequences | Limited on free | Use the contact view + `enrich_hook` for manual outreach |

---

## File Reference

| File | Purpose |
|---|---|
| `main.py` | Entry point: `--provision`, `--schedule`, or bare run |
| `scoring/engine.py` | Flare federal ICP weights, hook templates, title inference |
| `enrichment/pipeline.py` | Fetch → enrich → score → hook → write to SQLite & HubSpot |
| `hubspot/sync.py` | HubSpot batch read/write with rate-limit guards |
| `hubspot/properties.py` | One-time provisioning of 10 custom properties |
| `db/schema.py` | SQLite tables: lead_records, scoring_history, api_usage_log |
| `targets/flare_federal_targets.csv` | Pre-researched federal targeting list |
| `targets/seed_hubspot.py` | One-time CSV → HubSpot loader |
