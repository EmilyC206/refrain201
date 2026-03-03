# Flare Federal Pipeline — Junior AE Demo Runbook
**Audience:** Junior Account Executive  
**Duration:** 25–30 minutes  
**Goal:** Show how a cold company name becomes a scored, personalized HubSpot contact — and how the AE works the resulting list to book meetings with the right federal buyers.

---

## Before You Start (Presenter Prep — 5 min)

Open these four things before the AE arrives:

1. **Terminal** in this project folder (for live commands)
2. **HubSpot Contacts** view, sorted by `lead_total_score` descending
3. **`targets/flare_federal_seed.csv`** open in a spreadsheet app (Numbers, Excel, or Google Sheets)
4. **`scoring/engine.py`** open in the editor

Confirm the pipeline is working with a quick sanity check:
```bash
python3 -c "
from scoring.engine import score_lead, build_personalization_hook
r = score_lead(industry='Federal Government', seniority='CXO', job_function='Cybersecurity', employee_range='1001+')
h, _ = build_personalization_hook(company_name='CISA', size_desc='enterprise', industry='Federal Government', job_function='Cybersecurity', seniority='CXO')
print('Score:', r['total_score'], '| Tier:', r['score_tier'])
print('Hook: ', h)
"
```
Expected output:
```
Score: 100 | Tier: Hot
Hook:  CISOs at Federal Government agencies are cutting dark-web exposure response time from weeks to hours with Flare.
```

---

## Part 1 — The Problem (3 min)

**Say this:**

> "Flare sells a dark-web monitoring platform to federal agencies and the defense contractors that serve them.
> The challenge for us as AEs is that we can't call the main number at the FBI and ask for the CISO.
> We need to know *who* to reach, *what* pain point to lead with, and *which* organizations to prioritize first.
>
> This pipeline solves all three problems automatically."

**Show:** `targets/flare_federal_seed.csv` in the spreadsheet.

Point out the columns:
- `company_name` / `domain` — who we're targeting
- `segment` — why (6 distinct federal buyer types)
- `sam_pattern` — the specific SAM.gov contract type that proves this org already buys this category
- `priority_tier` — our first guess at Hot/Warm/Cool before any enrichment
- `target_title` — the persona we're going after
- `personalization_angle` — the one-line reason Flare is relevant to that org

**Key talking point:**

> "Notice the `sam_pattern` column. Before we ever picked up the phone, we matched each org to a SAM.gov contract pattern — like 'brand_monitoring' for TSP or 'digital_surveillance' for the FBI. That means we know they already have budget for this category. We're not creating demand; we're finding existing demand."

---

## Part 2 — How the Scoring Engine Works (5 min)

**Show:** `scoring/engine.py` open in the editor.

Walk through the four scoring dimensions (100 pts total):

```
ICP Industry Fit:   40 pts  ← Is this org in a sector Flare sells to?
Seniority:          25 pts  ← Can this person sign a contract?
Job Function:       20 pts  ← Is this person a cyber/IT buyer?
Company Size:       15 pts  ← Is this org big enough to matter?
```

**Live demo — score three personas side by side:**

```bash
python3 -c "
from scoring.engine import score_lead, build_personalization_hook

personas = [
    dict(industry='Federal Government', seniority='CXO',      job_function='Cybersecurity', employee_range='1001+', label='FBI CISO'),
    dict(industry='Systems Integration', seniority='Director', job_function='Cybersecurity', employee_range='1001+', label='Booz Allen CTI Director'),
    dict(industry='Other',              seniority='IC',        job_function='Other',         employee_range='1-10',  label='Random startup IC'),
]
for p in personas:
    r = score_lead(industry=p['industry'], seniority=p['seniority'], job_function=p['job_function'], employee_range=p['employee_range'])
    print(f\"{p['label']:35} score={r['total_score']:3}  tier={r['score_tier']}\")
"
```

Expected output:
```
FBI CISO                            score=100  tier=Hot
Booz Allen CTI Director             score= 88  tier=Hot
Random startup IC                   score= 14  tier=Cold
```

**Ask the AE:**
> "Which one would you call first on a Monday morning?"

The answer is obvious. That's the point — the pipeline makes prioritization automatic, not a judgment call.

---

## Part 3 — The Personalization Hook (5 min)

**Say this:**

> "Scoring tells us who to call. The hook tells us what to say in the first line of an email.
> Every contact gets a unique opening sentence generated from their title, their company, and their industry."

**Live demo — generate hooks for three different personas:**

```bash
python3 -c "
from scoring.engine import build_personalization_hook

contacts = [
    dict(company_name='CISA',         size_desc='enterprise',  industry='Federal Government', job_function='Cybersecurity', seniority='CXO',      label='CISA CISO'),
    dict(company_name='Booz Allen',   size_desc='enterprise',  industry='Systems Integration',job_function='Engineering',   seniority='Director',  label='Booz Allen Eng Director'),
    dict(company_name='Secret Service',size_desc='enterprise', industry='Law Enforcement',    job_function='Operations',    seniority='Manager',   label='USSS Ops Manager'),
]
for c in contacts:
    hook, _ = build_personalization_hook(**{k: v for k,v in c.items() if k != 'label'})
    print(f\"{c['label']}:\")
    print(f'  \"{hook}\"')
    print()
"
```

**Key talking point:**

> "This sentence goes directly into the HubSpot email sequence as `{{ contact.enrich_hook }}`.
> The AE never writes it — it's already there when they open the contact record.
> Their job is to send the email and handle the reply, not write personalization from scratch 92 times."

---

## Part 4 — Live Pipeline Run (7 min)

**Say this:**

> "Let me show you what happens when a new contact enters the system."

**Step 1 — Add a test contact manually in HubSpot:**

Go to HubSpot → Contacts → Create contact.
Fill in:
- **Email:** `demo.ciso@fbi.gov`
- **Job Title:** `Chief Information Security Officer`
- **Company:** `Federal Bureau of Investigation`
- Leave `enrich_status` blank (pipeline will pick it up automatically)

**Step 2 — Run the pipeline:**

```bash
python3 main.py
```

Watch the terminal output together. Point out:
```
Found 1 contact(s) to process.
OK   <id> | demo.ciso@fbi.gov | score=100 tier=Hot
```

**Step 3 — Open the contact in HubSpot and show the AE what appeared:**

| Property | Value |
|---|---|
| `enrich_status` | Complete |
| `lead_total_score` | 100 |
| `lead_score_tier` | Hot |
| `enrich_seniority` | CXO |
| `enrich_function` | Cybersecurity |
| `enrich_hook` | *"CISOs at Law Enforcement agencies are cutting dark-web exposure response time from weeks to hours with Flare."* |

**Ask the AE:**

> "How long did that take from entering the email to having a scored, personalized contact ready to outreach?"

Answer: about 4 seconds.

> "Without this pipeline, how long would it take to manually research this contact, figure out what to say, and enter the data?"

Typical answer: 10–15 minutes per contact. Across 57 contacts, that's a full work day eliminated.

---

## Part 5 — Working the Hot List (5 min)

**Show:** HubSpot Contacts view, sorted by `lead_total_score` descending.

Walk the AE through the working rhythm:

**Morning routine (15 min):**
1. Open HubSpot → Contacts → "Hot Leads — AE Queue" list (`lead_score_tier = Hot AND enrich_status = Complete`)
2. Sort by `lead_total_score` descending — highest fit contacts first
3. Read the `enrich_hook` on each contact — that's your opening line
4. Send outreach or log a call task

**What to say in the email:**

> Subject: Dark-web exposure at [Company]

> [Paste `enrich_hook` here as the first sentence.]
>
> Flare gives your team a single view of credential leaks, doxxing threats, and dark-web chatter targeting [Company] — updated continuously, no manual searches required.
>
> Worth a 20-minute call this week?

**Tier routing:**

| Tier | Score | Who owns it | SLA |
|---|---|---|---|
| Hot ≥ 75 | 73 contacts | AE-owned | 2-day response |
| Warm 50–74 | 38 contacts | SDR sequence | 7-day sequence |
| Cool 25–49 | 7 contacts | Nurture email | Monthly touch |
| Cold < 25 | 1 contact | Suppress | Do not contact |

---

## Part 6 — Keeping It Fresh (2 min)

**Say this:**

> "The pipeline runs on a schedule. Every 4 hours it checks HubSpot for any new contacts without an enrichment status and scores them automatically. You never have to run it manually."

Show the command they'd use to start the scheduled daemon:

```bash
python3 main.py --schedule
```

And the watchdog alert that fires if anything breaks:

```bash
python3 watchdog.py
```

> "If a contact fails enrichment, or an API is near its daily cap, you get an email alert. The pipeline is self-monitoring."

---

## Common AE Questions & Answers

**Q: Are these real email addresses?**  
A: The seed list uses job-title-based placeholder addresses to seed the pipeline. When an SDR finds the actual named contact (via LinkedIn Sales Navigator, ZoomInfo, etc.), they replace the email in HubSpot and the pipeline re-enriches on the next run.

**Q: Why are some contacts Warm instead of Hot?**  
A: Usually because the job title keyword didn't map cleanly to a Cybersecurity or IT function, or the seniority inferred as Manager instead of Director. Click into the contact, check `enrich_seniority` and `enrich_function` — if they're wrong, update the job title in HubSpot and reset `enrich_status` to Pending to trigger a re-score.

**Q: What's a SAM pattern and why does it matter for my outreach?**  
A: SAM.gov is the federal procurement portal. Each contact's `sam_pattern` in the seed CSV tells you which type of contract this org has already issued for a tool like Flare. If the pattern is `brand_monitoring`, open the conversation with brand protection — you know they have budget for it. If it's `digital_surveillance`, lead with dark-web monitoring.

**Q: Can I add companies not on the seed list?**  
A: Yes. Add a contact in HubSpot with any `.gov`, `.mil`, or federal contractor domain — the pipeline will automatically look up the industry via our domain override map and score them correctly on the next run.

---

## Quick Reference Card (Print This for the AE)

```
PIPELINE COMMANDS
─────────────────────────────────────────────
Run once:          python3 main.py
Run on schedule:   python3 main.py --schedule
Provision HubSpot: python3 main.py --provision
Seed contacts:     python3 targets/seed_hubspot.py
Health check:      python3 watchdog.py

SCORE TIERS
─────────────────────────────────────────────
Hot  ≥ 75  → AE-owned. Call within 2 days.
Warm 50–74 → SDR sequence. 7-day outreach.
Cool 25–49 → Nurture. Monthly email only.
Cold  < 25 → Suppress. Do not contact.

PERSONALIZATION TOKEN (for email sequences)
─────────────────────────────────────────────
{{ contact.enrich_hook }}

TOP 10 PRIORITY CONTACTS (score 96–100)
─────────────────────────────────────────────
 100  CISA (Threat Hunting)
 100  OPM (CISO)
 100  SSA (CISO)
 100  VA (Threat Intel)
 100  CMS (CISO)
 100  IRS (CIO)
 100  Treasury (Deputy Asst. Secretary)
 100  Ed Dept (CISO)
  98  VA (Asst. Secretary IT/CIO)
  98  NSA (Cybersecurity Directorate)
```

---

*Demo built on the Flare Federal Targeting Pipeline. See README.md for full setup docs.*
