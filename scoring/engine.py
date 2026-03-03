from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# ICP Industry Fit weights (max 40 pts)
# Tuned for a B2B SaaS ICP selling to tech-adjacent companies.
# Adjust to match YOUR target market before going live.
# ──────────────────────────────────────────────────────────────────────────────
ICP_INDUSTRIES: dict[str, int] = {
    "SaaS": 40,
    "Software": 35,
    "Technology": 30,
    "Financial Services": 25,
    "Healthcare": 20,
    "E-Commerce": 15,
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
# Ranked by closed-deal frequency for B2B SaaS.
# ──────────────────────────────────────────────────────────────────────────────
FUNCTION_WEIGHTS: dict[str, int] = {
    "Marketing": 20,
    "Sales": 18,
    "Operations": 15,
    "Finance": 12,
    "Product": 10,
    "Engineering": 8,
    "Other": 3,
}

# ──────────────────────────────────────────────────────────────────────────────
# Company size weights (max 15 pts)
# Optimised for mid-market (51–1000) as primary ICP.
# ──────────────────────────────────────────────────────────────────────────────
SIZE_WEIGHTS: dict[str, int] = {
    "201-1000": 15,
    "51-200": 12,
    "1001+": 10,
    "11-50": 6,
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
    ("Marketing", "VP"):        "Revenue-focused marketing leaders at {company} are cutting CAC 30% with us.",
    ("Marketing", "Director"):  "Helping {company} scale demand gen without growing headcount.",
    ("Marketing", "CXO"):       "CMOs at {size_desc} companies like {company} are unifying pipeline attribution.",
    ("Marketing", "Manager"):   "Marketing managers at {industry} companies are automating lead scoring in days.",
    ("Marketing", "IC"):        "How {company}'s marketing team could automate their lead enrichment pipeline.",
    ("Sales", "VP"):            "VP Sales at {size_desc} {industry} companies compressing ramp time by 40%.",
    ("Sales", "CXO"):           "CROs at {industry} companies are using us to fix the forecast accuracy problem.",
    ("Sales", "Director"):      "Sales directors at {size_desc} companies are closing 2x faster with enriched data.",
    ("Sales", "Manager"):       "Sales managers at {company} are using enrichment to prioritize their pipeline.",
    ("Sales", "IC"):            "How reps at {industry} companies are hitting quota without more cold calls.",
    ("Operations", "CXO"):      "COOs at {size_desc} {industry} companies saving 15 hrs/week on manual ops work.",
    ("Operations", "VP"):       "VP Ops teams at {company} are eliminating data silos between CRM and outreach.",
    ("Operations", "Director"): "RevOps directors at {industry} companies reducing tool sprawl by 60%.",
    ("Operations", "Manager"):  "Ops managers at {size_desc} companies automating contact enrichment end-to-end.",
    ("Engineering", "CXO"):     "CTOs at {size_desc} {industry} startups saving 10 hrs/week on ops overhead.",
    ("Engineering", "VP"):      "Engineering VPs at {company} cutting integration maintenance by 50%.",
    ("Engineering", "Director"):"Engineering directors at {industry} companies shipping faster with cleaner data.",
    ("Finance", "CXO"):         "CFOs at {size_desc} {industry} companies tying pipeline to revenue in real time.",
    ("Finance", "VP"):          "VP Finance teams at {company} getting ROI clarity on every outreach dollar.",
    ("Product", "CXO"):         "CPOs at {industry} companies building with richer customer signal from day one.",
    ("Product", "VP"):          "VP Product at {size_desc} companies reducing churn through better ICP targeting.",
}

# ──────────────────────────────────────────────────────────────────────────────
# Keyword maps for title inference
# ──────────────────────────────────────────────────────────────────────────────
_SENIORITY_KEYWORDS: dict[str, list[str]] = {
    "CXO":      ["ceo", "cto", "cmo", "cro", "coo", "cfo", "chief", "founder", "co-founder", "president"],
    "VP":       ["vp ", "vice president", "vice-president"],
    "Director": ["director", "head of", "head,"],
    "Manager":  ["manager", "lead ", "principal", "staff "],
}

_FUNCTION_KEYWORDS: dict[str, list[str]] = {
    "Marketing":   ["marketing", "demand gen", "demand generation", "growth", "brand", "content", "seo", "campaigns"],
    "Sales":       ["sales", "account executive", " ae ", "sdr", "bdr", "business development", "revenue"],
    "Engineering": ["engineer", "developer", "software", "data", "ml ", "ai ", "architect", "devops", "sre"],
    "Finance":     ["finance", "financial", "accounting", "controller", "treasury", "fp&a"],
    "Operations":  ["operations", " ops", "revops", "revenue operations", "enablement", "strategy"],
    "Product":     ["product", " ux", " ui", "design", "research", " pm ", "program manager"],
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
