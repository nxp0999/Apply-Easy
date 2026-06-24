"""
filters.py
Pre-apply gates applied before AI processing.
A job that fails any filter is marked skipped (status=2) immediately
and never consumes a Groq/Ollama token.
"""

import re
from datetime import date as _date

# ── Company blacklist ──────────────────────────────────────────────────────────
# IT services / staffing-heavy firms that flood Naukri/LinkedIn but are not
# product/data-science companies. Extend freely.
COMPANY_BLACKLIST = [
    "tcs",
    "tata consultancy",
    "infosys",
    "wipro",
    "cognizant",
    "hcl",
    "tech mahindra",
    "mphasis",
    "hexaware",
    "capgemini",
    "accenture",
    "ibm india",
    "ltimindtree",
    "lti",
    "mindtree",
    "persistent systems",
    "niit technologies",
    "kpit",
]


def is_blacklisted(company: str) -> bool:
    """Return True if the company is on the blacklist."""
    c = company.lower()
    return any(b in c for b in COMPANY_BLACKLIST)


# ── Seniority filter ──────────────────────────────────────────────────────────
# Candidate has ~2.5 yrs industry + MS. Reject roles that demand > 5 yrs.
_YEARS_RE = re.compile(
    r'(\d+)\+?\s*(?:to\s*\d+\s*)?years?\s*(?:of\s*)?(?:relevant\s*)?experience',
    re.IGNORECASE,
)


def is_overleveled(jd: str) -> bool:
    """
    Return True if the job description requires more than 5 years of experience.
    Handles patterns like '6+ years', '6-8 years', '7 years of experience'.
    """
    matches = _YEARS_RE.findall(jd)
    return any(int(y) > 5 for y in matches)


# ── Location filter ──────────────────────────────────────────────────────────────
_INDIA_RE = re.compile(
    r'(india|bengaluru|bangalore|hyderabad|pune|mumbai|delhi|noida|gurgaon'
    r'|gurugram|chennai|kolkata|kochi|trivandrum|remote|anywhere|hybrid|pan.india'
    r'|karnataka|maharashtra|telangana|tamil.?nadu|kerala|rajasthan|gujarat'
    r'|,\s*in\b)',   # LinkedIn abbreviated format: "KA, IN", "MH, IN", etc.
    re.IGNORECASE,
)


def is_wrong_location(job_location: str, jd: str = "") -> bool:
    """
    Return True if job is clearly NOT in India or remote.
    Checks the location field first, then the first 400 chars of the JD.
    Empty location is treated as unknown (not filtered out).
    """
    if not job_location or job_location.lower() in ("", "none", "nan", "unknown"):
        return False  # can't confirm wrong — let it through
    text = job_location + " " + jd[:400]
    return not bool(_INDIA_RE.search(text))


# ── Keyword pre-scorer (cheap string match, zero LLM cost) ────────────────────
# Candidate's transferable skills. Any JD that mentions fewer than
# KEYWORD_PRESCORE_MIN (see config.py) of these is almost certainly off-domain
# and should be dropped before touching the LLM.
CANDIDATE_SKILLS = [
    # Core identity
    "python", "sql", "machine learning", "data science", "data engineer",
    "deep learning", "nlp", "neural network", "transformer", "llm", "generative ai",
    # Frameworks
    "pytorch", "tensorflow", "scikit", "sklearn", "xgboost", "lightgbm",
    "huggingface", "bert", "cnn", "rnn", "lstm",
    # Big data / DE
    "spark", "pyspark", "databricks", "hadoop", "hive", "kafka",
    "etl", "pipeline", "airflow", "dbt", "data warehouse",
    # Stats / DS methods
    "statistics", "regression", "classification", "clustering",
    "a/b test", "hypothesis", "time series", "forecasting",
    # Tools / infra
    "pandas", "numpy", "docker", "kubernetes", "git", "mlflow",
    "mongodb", "mysql", "postgres", "redis",
    "aws", "gcp", "azure", "cloud",
    # Analytics
    "analytics", "dashboard", "visualization", "tableau", "power bi",
    "api", "rest", "microservice",
    # General signals that indicate a tech/data role
    "model", "dataset", "feature", "training", "inference",
]


def keyword_prescore(jd: str, title: str = "") -> float:
    """
    Fraction of CANDIDATE_SKILLS that appear in (jd + title).
    Fast string search — no LLM, no network call.
    Returns 0.0 – 1.0.
    """
    text = (jd + " " + title).lower()
    matched = sum(1 for skill in CANDIDATE_SKILLS if skill in text)
    return matched / len(CANDIDATE_SKILLS)


# ── Title quality filter ───────────────────────────────────────────────────────
# Reject titles that are clearly off-target (trainer, tutor, sales, etc.)
_TITLE_REJECT = re.compile(
    r'\b(trainer|tutor|faculty|lecturer|professor|sales|marketing|recruiter'
    r'|content creator|seo|social media|copywriter|customer success'
    r'|account manager|business development)\b',
    re.IGNORECASE,
)


def is_off_target_title(title: str) -> bool:
    """Return True if the job title is clearly outside the target domain."""
    return bool(_TITLE_REJECT.search(title))


# ── Stale posting filter ───────────────────────────────────────────────────────
_STALE_DAYS = 21  # postings older than this are deprioritised


def is_stale_posting(date_posted) -> bool:
    """Return True if the posting is older than _STALE_DAYS days."""
    if not date_posted:
        return False
    try:
        posted = _date.fromisoformat(str(date_posted)[:10])
        return (_date.today() - posted).days > _STALE_DAYS
    except (ValueError, TypeError):
        return False


# ── Ghost job detector ────────────────────────────────────────────────────────
_GHOST_SIGNALS = [
    "no longer accepting", "position has been filled",
    "this job is closed", "this position is no longer",
    "job has expired", "role has been filled",
    "not accepting applications", "this listing has expired",
    "application deadline has passed", "vacancy has been closed",
    "job posting has been removed", "this role has been closed",
]


def is_ghost_job(jd: str) -> bool:
    """Return True if the JD text contains closure/ghost-job signals."""
    jd_lower = jd.lower()
    return any(s in jd_lower for s in _GHOST_SIGNALS)
