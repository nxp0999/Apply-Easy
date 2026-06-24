"""
pipeline/rule_scorer.py

Deterministic, zero-LLM fit scorer.
Replaces the LLM score_fit call with weighted rule-based scoring so
every job gets an instant, reproducible score without spending tokens.

Weights match the original LLM prompt:
  final_score = keyword_overlap*0.35 + title_match*0.20
              + experience_level*0.15 + tech_stack*0.20
              + location_match*0.10
"""

import re

from filters import CANDIDATE_SKILLS

# ── Tech tools subset (more specific than CANDIDATE_SKILLS) ────────────────
TECH_TOOLS = [
    "python", "sql", "pyspark", "spark", "pytorch", "tensorflow",
    "scikit-learn", "sklearn", "pandas", "numpy", "keras",
    "mlflow", "airflow", "dbt", "kafka", "docker", "kubernetes",
    "aws", "gcp", "azure", "databricks", "bigquery", "redshift",
    "snowflake", "hive", "hadoop", "git", "fastapi", "flask",
    "transformers", "hugging face", "huggingface", "langchain",
    "openai", "llm", "rag", "vector database", "pinecone", "weaviate",
    "xgboost", "lightgbm", "catboost", "statsmodels", "scipy",
    "tableau", "power bi", "looker", "streamlit", "gradio",
]

# ── Title tiers — ordered highest → lowest ─────────────────────────────────
_TITLE_TIERS: list[tuple[int, list[str]]] = [
    (100, [
        "data scientist", "machine learning engineer", "ml engineer",
        "ai engineer", "nlp engineer", "deep learning engineer",
        "applied scientist", "research scientist", "genai engineer",
        "generative ai", "llm engineer", "ai researcher",
    ]),
    (85, [
        "data engineer", "analytics engineer", "mlops engineer",
        "platform engineer", "ml platform", "ai platform",
    ]),
    (70, [
        "data analyst", "bi engineer", "business intelligence",
        "python developer", "python engineer", "software engineer",
        "backend engineer", "ml ops",
    ]),
    (45, [
        "full stack", "frontend", "devops", "cloud engineer",
        "java", "qa engineer", "test engineer",
    ]),
]


# ── Bonus / penalty signal lists ─────────────────────────────────────────

# Domains where candidate has strong project signal
_STRONG_DOMAINS = [
    "fintech", "finance", "banking", "financial services", "payments",
    "nlp", "natural language", "text analytics", "conversational ai",
    "database", "data platform", "data infrastructure",
]
# Domains where candidate signals are thin
_WEAK_DOMAINS = [
    "healthcare", "pharma", "clinical", "hospital",
    "supply chain", "logistics", "manufacturing", "retail",
    "ecommerce", "inventory", "procurement",
]

# Modern / recency-signal tools (exact match in JD → stronger than category hit)
_RECENCY_TOOLS = [
    "kafka", "spark structured streaming", "llm", "large language model",
    "rag", "retrieval augmented", "langchain", "vector database",
    "embedding", "huggingface", "hugging face", "transformers",
    "mlflow", "dbt", "airflow", "playwright",
]


# ── Helpers ────────────────────────────────────────────────────────────────

def _keyword_score(jd_lower: str) -> int:
    hits = sum(1 for s in CANDIDATE_SKILLS if s in jd_lower)
    frac = hits / len(CANDIDATE_SKILLS)
    # Scale: 0% → 0, 12% → 40, 21% → 70, 35%+ → 100
    return min(100, int(frac / 0.35 * 100))


def _title_score(title_lower: str) -> int:
    for score, keywords in _TITLE_TIERS:
        if any(kw in title_lower for kw in keywords):
            return score
    return 25


def _experience_score(jd_lower: str) -> int:
    # Underleveled floor: "entry level" / "fresher" / "0-1 years" is below
    # what an MS grad with 2.5 yrs industry experience should target.
    if any(t in jd_lower for t in ["entry level", "entry-level", "fresher",
                                    "0-1 year", "0 to 1 year"]):
        return 60   # floor — underleveled for MS + industry exp

    patterns = [
        r'(\d+)\s*\+\s*years?',
        r'(\d+)\s*(?:to|-)\s*\d+\s*years?',
        r'minimum\s+(\d+)\s+years?',
        r'at\s+least\s+(\d+)\s+years?',
        r'(\d+)\s+years?\s+(?:of\s+)?(?:experience|exp)',
    ]
    years = None
    for pat in patterns:
        m = re.search(pat, jd_lower)
        if m:
            years = int(m.group(1))
            break

    if years is None:
        return 75   # not stated — neutral
    if years <= 2:
        return 100
    if years <= 4:
        return 85
    if years == 5:
        return 60
    if years <= 7:
        return 35
    return 15       # 8+ years — very overleveled


def _tech_score(jd_lower: str) -> int:
    hits = sum(1 for t in TECH_TOOLS if t in jd_lower)
    frac = hits / len(TECH_TOOLS)
    return min(100, int(frac / 0.30 * 100))


def _location_score(location: str, jd_lower: str) -> int:
    preferred_cities = [
        "bengaluru", "bangalore", "hyderabad", "pune", "mumbai",
        "delhi", "ncr", "chennai",
    ]
    remote_signals = ["remote", "hybrid", "work from home", "wfh", "anywhere in india"]
    loc_lower = location.lower()

    city_match  = any(p in loc_lower for p in preferred_cities)
    remote_match = any(r in loc_lower or r in jd_lower for r in remote_signals)

    if city_match and remote_match:
        return 100   # ideal: preferred city + remote/hybrid option
    if city_match or "remote" in loc_lower:
        return 100
    if remote_match:
        return 95    # remote/hybrid explicitly stated in JD — strong positive
    if "india" in loc_lower:
        return 85
    if any(p in jd_lower for p in preferred_cities):
        return 70
    return 50


def _missing_keywords(jd_lower: str, resume_lower: str) -> list[str]:
    """Skills the JD wants that aren't in the resume — for tailoring injection."""
    return [
        s for s in CANDIDATE_SKILLS
        if s in jd_lower and s not in resume_lower
    ][:10]


def _gap_mitigations(gaps: list, jd_lower: str, resume_lower: str) -> list[str]:
    """For each gap, return a concrete 1-line action the candidate can take."""
    hints = []
    for gap in gaps:
        g = gap.lower()
        if "keyword" in g:
            missing = [s for s in CANDIDATE_SKILLS if s in jd_lower and s not in resume_lower]
            if missing:
                hints.append(f"Add to Skills section: {', '.join(missing[:4])}")
        elif "title" in g:
            hints.append("Reframe the role context in your first experience bullet to mirror the JD title")
        elif "overleveled" in g or "experience" in g:
            hints.append("Lead with breadth of projects to justify seniority gap")
        elif "tech stack" in g:
            thin = [t for t in TECH_TOOLS if t in jd_lower and t not in resume_lower]
            if thin:
                hints.append(f"Add to Skills: {', '.join(thin[:3])}")
        elif "domain" in g:
            hints.append("Open cover letter with transferable domain experience")
        elif "bachelor" in g:
            hints.append("Emphasise applied impact over degree level in summary")
    return hints[:3]


def _degree_bonus(jd_lower: str) -> int:
    """MS/master's mentioned positively → +8. Bachelor's-only JD → -5."""
    master_signals = ["master", "m.s.", "ms degree", "msc", "m.tech", "postgraduate",
                      "graduate degree", "post-graduate"]
    if any(s in jd_lower for s in master_signals):
        return 8
    # bachelor's explicitly required with no higher degree mentioned
    bachelor_only = ("bachelor" in jd_lower or "b.tech" in jd_lower or "b.e." in jd_lower)
    higher_ok     = any(s in jd_lower for s in master_signals + ["or higher", "or above",
                                                                   "or equivalent"])
    if bachelor_only and not higher_ok:
        return -5
    return 0


def _cert_bonus(jd_lower: str) -> int:
    """Databricks / Spark certification explicitly valued → +8."""
    cert_terms = ["certif", "certified", "certification", "professional"]
    if "databricks" in jd_lower and any(c in jd_lower for c in cert_terms):
        return 8
    if "spark certified" in jd_lower or "databricks certified" in jd_lower:
        return 8
    return 0


def _domain_bonus(jd_lower: str) -> int:
    """Projects in fintech/NLP/DB → +6. Thin-signal domains → -5."""
    if any(d in jd_lower for d in _STRONG_DOMAINS):
        return 6
    if any(d in jd_lower for d in _WEAK_DOMAINS):
        return -5
    return 0


def _recency_bonus(jd_lower: str) -> int:
    """Exact modern-tool hits are a stronger signal than generic keyword overlap."""
    hits = sum(1 for t in _RECENCY_TOOLS if t in jd_lower)
    if hits >= 3:
        return 6
    if hits >= 1:
        return 3
    return 0


def _strengths_gaps(
    kw: int, ti: int, exp: int, tech: int
) -> tuple[list[str], list[str]]:
    strengths, gaps = [], []
    if kw >= 70:
        strengths.append("strong keyword overlap with JD")
    if ti >= 85:
        strengths.append("title is a direct match")
    if exp >= 85:
        strengths.append("experience level is a good fit")
    if tech >= 70:
        strengths.append("tech stack aligns well")
    if kw < 50:
        gaps.append("low keyword coverage — few matching skills in JD")
    if ti < 70:
        gaps.append("job title diverges from candidate profile")
    if exp < 60:
        gaps.append("overleveled or underleveled experience requirement")
    if tech < 50:
        gaps.append("tech stack overlap is thin")
    return strengths or ["some relevant skills present"], gaps or ["no major gaps detected"]


# ── Public API ─────────────────────────────────────────────────────────────

def score_fit_rules(job: dict, base_resume: str) -> dict:
    """
    Score the job against the candidate profile using deterministic rules.
    Returns a dict with the same shape as the LLM score_fit output so the
    rest of the pipeline is unchanged.
    """
    title     = (job.get("title", "") or "").lower()
    jd_raw    = (job.get("description", "") or "")
    jd        = jd_raw.lower()
    location  = (job.get("location", "") or "")
    resume_lc = base_resume.lower()

    kw   = _keyword_score(jd)
    ti   = _title_score(title)
    exp  = _experience_score(jd)
    tech = _tech_score(jd)
    loc  = _location_score(location, jd)

    base  = int(kw * 0.35 + ti * 0.20 + exp * 0.15 + tech * 0.20 + loc * 0.10)

    # ── Targeted bonuses / penalties (capped 0-100) ──────────────────────
    degree  = _degree_bonus(jd)
    cert    = _cert_bonus(jd)
    domain  = _domain_bonus(jd)
    recency = _recency_bonus(jd)
    bonus   = degree + cert + domain + recency

    final = max(0, min(100, base + bonus))

    strengths, gaps = _strengths_gaps(kw, ti, exp, tech)
    if cert > 0:
        strengths.append("Databricks/Spark cert explicitly valued")
    if degree > 0:
        strengths.append("master's degree preferred or required")
    if domain > 0:
        strengths.append("domain aligns with candidate project experience")
    if recency > 0:
        strengths.append("JD uses modern tools matching candidate's stack")
    if degree < 0:
        gaps.append("JD seems bachelor's-only — MS may be overqualified")
    if domain < 0:
        gaps.append("domain is outside candidate's project experience")

    if final >= 80:
        verdict = "Strong match — proceed to tailor"
    elif final >= 70:
        verdict = "Good match — worth tailoring"
    elif final >= 55:
        verdict = "Moderate match — borderline"
    else:
        verdict = "Weak match — likely not worth applying"

    missing = _missing_keywords(jd, resume_lc)
    mitigations = _gap_mitigations(gaps, jd, resume_lc)

    return {
        "score":            final,
        "keyword_overlap":  kw,
        "title_match":      ti,
        "experience_level": exp,
        "tech_stack":       tech,
        "location_match":   loc,
        "bonuses":          {"degree": degree, "cert": cert,
                             "domain": domain, "recency": recency},
        "verdict":          verdict,
        "strengths":        strengths,
        "gaps":             gaps,
        "missing_keywords": missing,
        "mitigations":      mitigations,
    }
