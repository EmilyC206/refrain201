from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# ICP Industry Fit weights (max 40 pts)
# Tuned for IlluminationDevice's federal cybersecurity / dark-web intelligence ICP.
# ──────────────────────────────────────────────────────────────────────────────
ICP_INDUSTRIES: dict[str, int] = {
    "Federal Government / Defense": 40,
    "Law Enforcement": 40,
    "Cybersecurity": 38,
    "Managed Security Services": 35,
    "System Integration / Federal IT": 30,
    "Financial Services": 22,
    "Technology": 15,
    "Other": 3,
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
# Ranked by IlluminationDevice's federal champion personas: security and threat-intel
# buyers, then IT/eng who integrate, then ops/procurement who purchase.
# ──────────────────────────────────────────────────────────────────────────────
FUNCTION_WEIGHTS: dict[str, int] = {
    "Security": 20,
    "Threat Intelligence": 20,
    "IT / Engineering": 18,
    "Operations": 15,
    "Procurement / Contracting": 12,
    "Marketing": 10,
    "Sales": 10,
    "Other": 3,
}

# ──────────────────────────────────────────────────────────────────────────────
# Company size weights (max 15 pts)
# Reoriented toward enterprise-scale federal buyers and large primes.
# ──────────────────────────────────────────────────────────────────────────────
SIZE_WEIGHTS: dict[str, int] = {
    "1001+": 15,
    "201-1000": 13,
    "51-200": 8,
    "11-50": 4,
    "1-10": 1,
    "Unknown": 1,
}

# ──────────────────────────────────────────────────────────────────────────────
# Tier thresholds
# ──────────────────────────────────────────────────────────────────────────────
TIER_THRESHOLDS: dict[str, int] = {
    "Hot": 75,
    "Warm": 50,
    "Cool": 25,
}

SIZE_DESCRIPTIONS: dict[str, str] = {
    "1-10": "boutique",
    "11-50": "emerging",
    "51-200": "growth-stage",
    "201-1000": "mid-tier",
    "1001+": "enterprise",
}

# ──────────────────────────────────────────────────────────────────────────────
# Personalization hook templates keyed by (job_function, seniority).
# Available variables: {company}, {size_desc}, {industry}
# DO NOT rename these variables — build_personalization_hook() uses .format()
# ──────────────────────────────────────────────────────────────────────────────
HOOK_TEMPLATES: dict[tuple[str, str], str] = {
    # Security
    ("Security", "CXO"):       "CISOs at {company} are using IlluminationDevice to surface credential leaks and dark-web threats before adversaries act.",
    ("Security", "VP"):        "VP Security teams at {size_desc} {industry} organizations are cutting threat triage time 60% with IlluminationDevice.",
    ("Security", "Director"):  "Security directors at {company} are replacing manual dark-web monitoring with continuous automated detection.",
    ("Security", "Manager"):   "Security managers at {industry} agencies are getting analyst-ready dark-web alerts — no more noise.",
    ("Security", "IC"):        "How analysts at {company} are getting actionable dark-web intelligence without extra headcount.",
    # Threat Intelligence
    ("Threat Intelligence", "CXO"):       "CTI leaders at {company} are force-multiplying their analysts with IlluminationDevice's automated dark-web collection.",
    ("Threat Intelligence", "VP"):        "VP Threat Intel at {size_desc} {industry} organizations are eliminating blind spots across paste sites, forums, and marketplaces.",
    ("Threat Intelligence", "Director"):  "Threat intel directors at {company} are detecting credential exposures and brand abuse in hours, not weeks.",
    ("Threat Intelligence", "Manager"):   "CTI managers at {industry} agencies are automating the collection their team used to do manually.",
    ("Threat Intelligence", "IC"):        "How threat analysts at {company} are spending less time collecting and more time hunting.",
    # IT / Engineering
    ("IT / Engineering", "CXO"):       "CTOs at {size_desc} {industry} organizations are integrating IlluminationDevice's dark-web feed directly into their SIEM/SOAR stack.",
    ("IT / Engineering", "VP"):        "VP Engineering at {company} are closing the gap between external threat data and internal detection logic.",
    ("IT / Engineering", "Director"):  "IT directors at {industry} agencies are deploying IlluminationDevice's API to enrich alerts with dark-web context automatically.",
    ("IT / Engineering", "Manager"):   "Engineering leads at {company} are integrating IlluminationDevice in days — not months — with pre-built connectors.",
    # Operations
    ("Operations", "CXO"):       "COOs at {size_desc} {industry} organizations are reducing manual threat-monitoring overhead by 70% with IlluminationDevice.",
    ("Operations", "VP"):        "VP Ops teams at {company} are unifying dark-web, brand-monitoring, and credential-leak workflows in one platform.",
    ("Operations", "Director"):  "Operations directors at {industry} agencies are automating the threat-intel pipeline end to end.",
    ("Operations", "Manager"):   "Ops managers at {company} are eliminating spreadsheet-based threat tracking with IlluminationDevice's continuous monitoring.",
    # Procurement / Contracting
    ("Procurement / Contracting", "CXO"):       "Procurement executives at {company} are streamlining dark-web intelligence acquisition through existing vehicles.",
    ("Procurement / Contracting", "VP"):        "VP Contracting at {size_desc} {industry} organizations are adding IlluminationDevice to BPAs and IDIQs for immediate analyst access.",
    ("Procurement / Contracting", "Director"):  "Contracting directors at {company} are enabling threat-intel teams with IlluminationDevice via GSA Schedule or micro-purchase.",
    ("Procurement / Contracting", "Manager"):   "Contracting officers at {industry} agencies are evaluating IlluminationDevice's dark-web platform for existing cyber task orders.",
    # Marketing / Sales (for primes and channel partners)
    ("Marketing", "VP"):        "Marketing leaders at {company} are positioning IlluminationDevice's dark-web intelligence as a key differentiator in federal proposals.",
    ("Marketing", "Director"):  "Marketing directors at {size_desc} {industry} primes are using IlluminationDevice to strengthen their cyber recompete narratives.",
    ("Marketing", "Manager"):   "Marketing managers at {company} are building IlluminationDevice-powered case studies that win federal cyber deals.",
    ("Sales", "VP"):            "VP Sales at {size_desc} {industry} primes are embedding IlluminationDevice into proposals to win cyber task orders.",
    ("Sales", "CXO"):           "CROs at {industry} integrators are using IlluminationDevice as a subcontract differentiator on federal cyber recompetes.",
    ("Sales", "Director"):      "Sales directors at {company} are closing federal cyber deals faster by teaming with IlluminationDevice.",
    ("Sales", "Manager"):       "Account managers at {industry} primes are adding IlluminationDevice's dark-web monitoring to existing SOC contracts.",
}

# ──────────────────────────────────────────────────────────────────────────────
# Keyword maps for title inference
# ──────────────────────────────────────────────────────────────────────────────
_SENIORITY_KEYWORDS: dict[str, list[str]] = {
    "CXO":      [" ceo", " cto ", " cmo", " cro", " coo", " cfo", " ciso",
                 "chief information", "chief technology", "chief security",
                 "chief marketing", "chief revenue", "chief operating",
                 "chief financial", "chief executive", "chief data", "chief digital",
                 "founder", "co-founder", "president"],
    "VP":       ["vp ", "vice president", "vice-president"],
    "Director": ["director", "head of", "head,", "section chief", "branch chief",
                 "division chief", "special agent in charge", "intelligence director"],
    "Manager":  ["manager", "lead ", "principal", "staff ", "program manager",
                 "contracting officer"],
}

_FUNCTION_KEYWORDS: dict[str, list[str]] = {
    "Procurement / Contracting": ["procurement", "contracting officer", "contracting", "acquisition", "purchasing"],
    "Security":                ["security", "ciso", "infosec", "information security", "cybersecurity", "cyber security", " cyber ", "cyber ", "soc "],
    "Threat Intelligence":     ["threat intel", "threat intelligence", " cti ", "dark web", "dark-web", "osint", "intelligence analyst", "cyber intel", "intelligence director"],
    "IT / Engineering":        ["engineer", "developer", "software", "data", "ml ", "ai ", "architect", "devops", "sre", " it ", "information technology", "systems admin"],
    "Operations":              ["operations", " ops", "revops", "revenue operations", "enablement", "strategy"],
    "Marketing":               ["marketing", "demand gen", "demand generation", "growth", "brand", "content", "seo", "campaigns"],
    "Sales":                   ["sales", "account executive", " ae ", "sdr", "bdr", "business development", "revenue"],
}


def infer_seniority(title: str) -> str:
    """Infers seniority tier from a raw job title string."""
    t = " " + (title or "").lower()
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
        "company":   company_name or "your agency",
        "size_desc": size_desc or "growing",
        "industry":  industry or "federal",
    }
    return template.format(**variables), variables
