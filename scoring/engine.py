from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# ICP Industry Fit weights (max 40 pts)
# Tuned for Flare.io's federal go-to-market: government agencies, defense,
# law enforcement, and the systems integrators / MSSPs that serve them.
# ──────────────────────────────────────────────────────────────────────────────
ICP_INDUSTRIES: dict[str, int] = {
    "Federal Government": 40,
    "Defense": 38,
    "Law Enforcement": 36,
    "Financial Regulation": 30,
    "Systems Integration": 28,
    "Managed Security": 25,
    "Intelligence": 38,
    "Cybersecurity": 32,
    "Financial Services": 20,
    "Healthcare": 12,
    "Other": 5,
}

# ──────────────────────────────────────────────────────────────────────────────
# Seniority weights (max 25 pts)
# ──────────────────────────────────────────────────────────────────────────────
SENIORITY_WEIGHTS: dict[str, int] = {
    "CXO": 25,
    "VP": 22,
    "Director": 18,
    "Manager": 10,
    "IC": 4,
}

# ──────────────────────────────────────────────────────────────────────────────
# Job function weights (max 20 pts)
# Ranked by deal-close frequency for a cyber threat-intel platform.
# Cybersecurity and IT buyers are the primary economic buyers; Procurement
# controls the contract vehicle — both score at the top.
# ──────────────────────────────────────────────────────────────────────────────
FUNCTION_WEIGHTS: dict[str, int] = {
    "Cybersecurity": 20,
    "IT": 18,
    "Operations": 15,
    "Procurement": 14,
    "Engineering": 12,
    "Finance": 8,
    "Other": 3,
}

# ──────────────────────────────────────────────────────────────────────────────
# Company size weights (max 15 pts)
# Federal agencies and large primes are 1001+; mid-tier MSSPs are 201-1000.
# ──────────────────────────────────────────────────────────────────────────────
SIZE_WEIGHTS: dict[str, int] = {
    "1001+": 15,
    "201-1000": 12,
    "51-200": 8,
    "11-50": 4,
    "1-10": 2,
    "Unknown": 2,   # fallback when employee_range is not available
}

# ──────────────────────────────────────────────────────────────────────────────
# Tier thresholds — lower Hot threshold if >15% of leads land there.
# ──────────────────────────────────────────────────────────────────────────────
TIER_THRESHOLDS: dict[str, int] = {
    "Hot": 75,
    "Warm": 50,
    "Cool": 25,
}

SIZE_DESCRIPTIONS: dict[str, str] = {
    "1-10": "early-stage",
    "11-50": "seed-stage",
    "51-200": "growth-stage",
    "201-1000": "mid-market",
    "1001+": "enterprise",
}

# ──────────────────────────────────────────────────────────────────────────────
# Personalization hook templates keyed by (job_function, seniority).
# Available variables: {company}, {size_desc}, {industry}
# DO NOT rename these variables — build_personalization_hook() uses .format()
# ──────────────────────────────────────────────────────────────────────────────
HOOK_TEMPLATES: dict[tuple[str, str], str] = {
    # Cybersecurity buyers — primary economic buyers for Flare
    ("Cybersecurity", "CXO"):       "CISOs at {industry} agencies are cutting dark-web exposure response time from weeks to hours with Flare.",
    ("Cybersecurity", "VP"):        "Cyber leaders at {company} are force-multiplying their CTI team without adding headcount.",
    ("Cybersecurity", "Director"):  "CTI directors at {industry} organizations are reclaiming 1,500+ analyst hours per year using Flare's automated dark-web monitoring.",
    ("Cybersecurity", "Manager"):   "SOC managers at {size_desc} {industry} teams are eliminating manual dark-web triage with Flare's AI-prioritized alerts.",
    ("Cybersecurity", "IC"):        "How analysts at {company} are cutting credential-leak detection from days to minutes.",
    # IT buyers — often the technical champion or program owner
    ("IT", "CXO"):                  "CIOs at {industry} agencies are consolidating external threat visibility into a single pane of glass with Flare.",
    ("IT", "VP"):                   "IT leaders at {company} are closing vendor-risk blind spots across clear, deep, and dark web in one subscription.",
    ("IT", "Director"):             "IT security directors at {size_desc} {industry} organizations are operationalizing continuous threat exposure management.",
    ("IT", "Manager"):              "IT program managers at {company} are meeting CTEM mandates without standing up additional tooling.",
    ("IT", "IC"):                   "How {company}'s IT security team could automate external attack-surface monitoring end to end.",
    # Operations — mission-support and SOC operations leads
    ("Operations", "CXO"):          "COOs at {size_desc} {industry} agencies are reducing fraud and impersonation incidents against public-facing programs.",
    ("Operations", "VP"):           "Ops leaders at {company} are protecting brand integrity and citizen-facing portals from phishing and domain abuse.",
    ("Operations", "Director"):     "Operations directors at {industry} organizations are automating brand-monitoring enforcement previously done manually.",
    ("Operations", "Manager"):      "Ops managers at {size_desc} agencies are cutting response time on impersonation and phishing domains to under 24 hours.",
    # Procurement — contracting officers and acquisition leads
    ("Procurement", "CXO"):         "Acquisition executives at {industry} agencies are streamlining dark-web and brand-monitoring into a single SAM-compliant subscription.",
    ("Procurement", "Director"):    "Contracting directors at {company} are consolidating digital-surveillance and threat-intel buys under NAICS 541519.",
    ("Procurement", "Manager"):     "Contracting officers at {size_desc} {industry} agencies are finding Flare fits existing threat-intel and brand-monitoring SOWs.",
    ("Procurement", "IC"):          "How {company}'s acquisition team can structure a Flare subscription under current cyber and intelligence vehicle types.",
    # Engineering — technical evaluators at primes and MSSPs
    ("Engineering", "CXO"):         "CTOs at {size_desc} systems integrators are embedding Flare's dark-web engine into their managed detection offerings.",
    ("Engineering", "VP"):          "Engineering VPs at {company} are reducing custom dark-web tooling by 60% by adopting Flare as a core data source.",
    ("Engineering", "Director"):    "Engineering directors at {industry} primes are accelerating CTI platform build-outs with Flare's API-first architecture.",
    ("Engineering", "Manager"):     "Integration managers at {company} are connecting Flare to existing SIEM and SOAR stacks in under a week.",
    # Finance — budget owners at larger agencies and integrators
    ("Finance", "CXO"):             "CFOs at {size_desc} {industry} organizations are justifying cyber investment with Flare's measurable analyst-hours-saved metrics.",
    ("Finance", "VP"):              "Finance VPs at {company} are tying dark-web monitoring ROI to reduced fraud and incident-response costs.",
}

# ──────────────────────────────────────────────────────────────────────────────
# Keyword maps for title inference
# Expanded to capture federal and cyber-specific title patterns.
# ──────────────────────────────────────────────────────────────────────────────
_SENIORITY_KEYWORDS: dict[str, list[str]] = {
    "CXO":      [
        "ceo", "cto", "cmo", "cro", "coo", "cfo", "ciso", "cso",
        "chief", "founder", "co-founder", "president", "secretary",
        "administrator", "commissioner", "director general",
    ],
    "VP":       ["vp ", "vice president", "vice-president", "deputy director", "deputy secretary"],
    "Director": ["director", "head of", "head,", "superintendent", "special agent in charge"],
    "Manager":  ["manager", "lead ", "principal", "staff ", "program manager", "contracting officer"],
}

_FUNCTION_KEYWORDS: dict[str, list[str]] = {
    "Cybersecurity": [
        "cyber", "ciso", "cso", "soc", "cti", "threat intel", "threat intelligence",
        "dark web", "security operations", "incident response", "infosec",
        "information security", "vulnerability", "penetration", "red team",
        "digital forensics", "fraud prevention", "brand protection",
    ],
    "IT": [
        "information technology", " it ", "it director", "it manager", "cio",
        "network", "systems administrator", "infrastructure", "cloud", "devops",
        "sre", "architect", "platform", "data center",
    ],
    "Operations": [
        "operations", " ops", "mission", "intelligence operations",
        "law enforcement", "investigations", "special agent",
        "fraud", "compliance", "risk", "brand monitoring",
    ],
    "Procurement": [
        "procurement", "acquisition", "contracting", "contract officer",
        "contracting officer", "purchasing", "vendor management", "supply chain",
        "category manager", "grants",
    ],
    "Engineering": [
        "engineer", "developer", "software", "data", "ml ", "ai ", "architect",
        "integration", "api", "backend", "frontend",
    ],
    "Finance": [
        "finance", "financial", "accounting", "controller", "treasury",
        "fp&a", "budget", "cost",
    ],
}


def infer_seniority(title: str) -> str:
    """Infers seniority tier from a raw job title string."""
    t = (title or "").lower()
    for tier, keywords in _SENIORITY_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return tier
    return "IC"


def infer_job_function(title: str) -> str:
    """Infers department from a raw job title string."""
    t = (title or "").lower()
    for function, keywords in _FUNCTION_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return function
    return "Other"


def _tier_from_score(score: int) -> str:
    if score >= TIER_THRESHOLDS["Hot"]:
        return "Hot"
    if score >= TIER_THRESHOLDS["Warm"]:
        return "Warm"
    if score >= TIER_THRESHOLDS["Cool"]:
        return "Cool"
    return "Cold"


def score_lead(
    *,
    industry: str | None,
    seniority: str | None,
    job_function: str | None,
    employee_range: str | None,
) -> dict:
    """
    Returns sub-scores, total score, and tier.
    All inputs are optional. Missing signals fall back to their respective
    minimum-confidence bucket: Other (industry/function), IC (seniority),
    Unknown (company size) — never a hard zero.
    """
    s_icp      = ICP_INDUSTRIES.get(industry or "", ICP_INDUSTRIES["Other"])
    s_seniority = SENIORITY_WEIGHTS.get(seniority or "", SENIORITY_WEIGHTS["IC"])
    s_function  = FUNCTION_WEIGHTS.get(job_function or "", FUNCTION_WEIGHTS["Other"])
    s_size      = SIZE_WEIGHTS.get(employee_range or "", SIZE_WEIGHTS["Unknown"])
    total       = s_icp + s_seniority + s_function + s_size
    return {
        "score_icp_fit":      s_icp,
        "score_seniority":    s_seniority,
        "score_function":     s_function,
        "score_company_size": s_size,
        "total_score":        total,
        "score_tier":         _tier_from_score(total),
    }


def build_personalization_hook(
    *,
    company_name: str | None,
    size_desc: str | None,
    industry: str | None,
    job_function: str | None,
    seniority: str | None,
) -> tuple[str, dict]:
    """
    Looks up the best template for (job_function, seniority), fills variables.
    Falls back through seniority tiers when an exact pair is missing.
    Returns (hook_text, variables_dict).
    """
    fn  = job_function or "Other"
    sen = seniority or "IC"

    template = HOOK_TEMPLATES.get((fn, sen), "")
    if not template:
        for fallback in ("Manager", "Director", "VP", "IC"):
            template = HOOK_TEMPLATES.get((fn, fallback), "")
            if template:
                break

    if not template:
        return "", {}

    variables = {
        "company":   company_name or "your company",
        "size_desc": size_desc or "growing",
        "industry":  industry or "B2B",
    }
    return template.format(**variables), variables
