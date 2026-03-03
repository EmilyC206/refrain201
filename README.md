## HubSpot Cold Lead Enrichment & Scoring Tool
**A Revenue Operations pipeline that turns a cold email address into a scored, personalized, and routed HubSpot contact — using HubSpot's free tier and OSINT sources.**

### What this does (end-to-end)
- **Input**: an email address (optionally name + a few hints)
- **Enrich**: derive company + website context from the email’s domain (OSINT)
- **Score**: compute a transparent \(0-100\) fit score against your ICP config
- **Personalize**: generate 1–2 first-line “hooks” from verifiable enrichment signals
- **Sync**: upsert a HubSpot Contact, write enrichment properties, assign owner/tier
- **Audit**: persist runs + raw source payloads in SQLite for troubleshooting

### Architecture overview
- **CLI** (`coldlead`): runs the pipeline and provisioning commands
- **SQLite** (`./data/coldlead.sqlite`): lead + run history + cached responses
- **OSINT enrichers**:
  - Website fetch + metadata extraction
  - Tech detection (Wappalyzer signatures)
  - Wikidata org lookup (official website → org facts when available)
  - DNS signals (MX / A records)
- **HubSpot adapter**: free-tier compatible (Contacts + custom properties only)

### Project structure
```
.
├─ src/coldlead/
│  ├─ cli.py
│  ├─ config.py
│  ├─ db.py
│  ├─ pipeline.py
│  ├─ scoring.py
│  ├─ personalize.py
│  ├─ hubspot.py
│  └─ enrich/
│     ├─ website.py
│     ├─ dns_signals.py
│     ├─ wappalyze.py
│     └─ wikidata.py
├─ data/               # created at runtime
├─ .env.example
├─ pyproject.toml
└─ README.md
```

### Database schema (SQLite)
- **leads**: canonical lead identity (email, domain, name guesses)
- **runs**: one pipeline execution per email, with timestamps + status
- **enrichment_cache**: cached HTTP responses by URL + etag-ish fields
- **artifacts**: JSON blobs (raw OSINT, scoring breakdown, personalization hooks)

### Scoring model (transparent, configurable)
Score is \(0-100\), computed as a weighted sum of signals:
- **Email quality (0–25)**: corporate domain vs free mailbox, MX present
- **Company presence (0–25)**: reachable website, meaningful meta description, social links
- **ICP match (0–35)**: industry keywords + technology signals + country/region (if known)
- **Seniority hints (0–15)**: title keywords if provided; otherwise 0

All weights + keyword lists live in `coldlead.yaml` (generated on first run).

### Personalization hook system (no AI required)
Hooks are short strings sourced from:
- page title / meta description
- detected technologies
- “about”/careers signals (when discoverable from homepage links)
- Wikidata descriptions (when domain maps cleanly)

Hooks are produced via deterministic “hook generators” ranked by confidence.

### HubSpot free tier constraints (and workarounds)
- **No workflows / programmable automation** → this tool performs routing directly by setting:
  - `hubspot_owner_id` (optional) and/or a `coldlead_routing_tier` property
- **No custom objects** → everything stored on **Contact properties** + local SQLite audit log
- **Property provisioning** → a CLI command creates required Contact properties once

### Environment setup
1) Create a virtualenv and install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

2) Copy env template:

```bash
cp .env.example .env
```

3) Put your HubSpot private app token into `.env`:
- `HUBSPOT_PRIVATE_APP_TOKEN=...`

### First-time HubSpot property provisioning

```bash
coldlead hubspot provision-properties
```

### Running the pipeline

```bash
coldlead run --email "jane@acme.com" --first "Jane" --last "Doe"
```

### Verify it’s working
- **CLI output** shows enrichment summary, score, chosen hook(s), and HubSpot contact ID
- In HubSpot Contact record, you should see:
  - `coldlead_score`, `coldlead_score_breakdown`
  - `coldlead_personalization_hook`
  - `coldlead_last_enriched_at`, `coldlead_source_summary`

### Rules you must never break
- Never store secrets in git (no `.env` commits).
- Never scrape sites that explicitly disallow automated access; keep requests low-rate.
- Keep all scoring explainable (store a breakdown).
