import os

# ── Secrets (gitignored) ─────────────────────────────────────────────────────
try:
    import importlib
    _s = importlib.import_module("_local")   # loads _local.py from project root
    _SECRETS_EMAIL    = getattr(_s, "EMAIL", "")
    _SECRETS_PASSWORD = getattr(_s, "PASSWORD", "")
    _SECRETS_GROQ     = getattr(_s, "GROQ_API_KEY", "")
    _SECRETS_ANTHROPIC= getattr(_s, "ANTHROPIC_API_KEY", "")
    _SECRETS_LI_EMAIL    = getattr(_s, "LINKEDIN_EMAIL",    _SECRETS_EMAIL)
    _SECRETS_LI_PASSWORD = getattr(_s, "LINKEDIN_PASSWORD", _SECRETS_PASSWORD)
    _SECRETS_IN_EMAIL    = getattr(_s, "INDEED_EMAIL",      _SECRETS_EMAIL)
    _SECRETS_IN_PASSWORD = getattr(_s, "INDEED_PASSWORD",   _SECRETS_PASSWORD)
except Exception:
    _SECRETS_EMAIL = _SECRETS_PASSWORD = _SECRETS_GROQ = _SECRETS_ANTHROPIC = ""
    _SECRETS_LI_EMAIL = _SECRETS_LI_PASSWORD = ""
    _SECRETS_IN_EMAIL = _SECRETS_IN_PASSWORD = ""

# ── Anthropic ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = _SECRETS_ANTHROPIC or os.getenv("ANTHROPIC_API_KEY", "")

# ── Groq (primary AI engine for processing) ────────────────────────────────
GROQ_API_KEY = _SECRETS_GROQ or os.getenv("GROQ_API_KEY", "")

# ── YOUR BASE RESUME ───────────────────────────────────────────────────────
RESUME_PDF_PATH = "my_resume.pdf"

# def _load_resume(pdf_path: str) -> str:
#     """Extract text from resume PDF automatically."""
#     import os
#     if not os.path.exists(pdf_path):
#         raise FileNotFoundError(
#             f"Resume PDF not found: {pdf_path}\n"
#             f"Drop your resume PDF into the project folder and update RESUME_PDF_PATH in config.py"
#         )
#     try:
#         import pdfplumber
#         with pdfplumber.open(pdf_path) as pdf:
#             pages = [page.extract_text() or "" for page in pdf.pages]
#             return "\n".join(pages).strip()
#     except ImportError:
#         raise ImportError("Run: pip install pdfplumber")

# BASE_RESUME = _load_resume(RESUME_PDF_PATH)

def _clean_resume(text: str) -> str:
    """Fix known issues in extracted resume text before AI uses it."""
    fixes = [
        # Fix date format — standardize to long month names
        ("Jan ", "January "),
        ("Feb ", "February "),
        ("Mar ", "March "),
        ("Apr ", "April "),
        ("Jun ", "June "),
        ("Jul ", "July "),
        ("Aug ", "August "),
        ("Sep ", "September "),
        ("Oct ", "October "),
        ("Nov ", "November "),
        ("Dec ", "December "),

        # GlobalRides — 4 distinct bullets covering different themes
        ("Built predictive models using historical order data to forecast demand patterns",
        "Forecasted demand patterns across 12 restaurants and 11 ride routes by applying time-series analysis on 260+ historical orders, improving resource allocation efficiency by 23%"),

        ("Analyzed 260+ orders to identify customer segmentation",
        "Segmented customers into behavioral cohorts using SQL aggregations, identifying that power users (15+ orders) generated $1,694 revenue at 4.2/5.0 satisfaction rating"),

        ("Designed relational database with 26 normalized tables",
        "Architected a 26-table MySQL relational database with Boyce-Codd Normal Form normalization, supporting concurrent food and ride operations across 12 restaurants and 11 ride routes"),

        ("achieved 95%+ order fulfillment within SLA",
        "Optimized query performance through indexing and structured joins, achieving 95%+ order fulfillment within Service Level Agreement windows"),
    ]
    for old, new in fixes:
        text = text.replace(old, new)
    return text


RESUME_TEX_PATH = "my_resume.tex"   # preferred source — cleaner text than PDF


def _load_resume(pdf_path: str) -> str:
    import os
    # Prefer .tex if present — higher fidelity than PDF extraction
    tex_path = os.path.splitext(pdf_path)[0] + ".tex"
    if os.path.exists(RESUME_TEX_PATH):
        from pipeline.tex_parser import load_tex_resume
        return load_tex_resume(RESUME_TEX_PATH)
    if os.path.exists(tex_path):
        from pipeline.tex_parser import load_tex_resume
        return load_tex_resume(tex_path)
    if not os.path.exists(pdf_path):
        import warnings
        warnings.warn(
            f"Resume not found ({RESUME_TEX_PATH} or {pdf_path}) — pipeline will fail.",
            stacklevel=2,
        )
        return ""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
            text = "\n".join(pages).strip()
            return _clean_resume(text)
    except ImportError:
        raise ImportError("Run: pip install pdfplumber")


BASE_RESUME = _load_resume(RESUME_PDF_PATH)



# ── Job sources — edit these to change what gets scraped ──────────────────
JOB_BOARDS = [
    "linkedin",   # Tier 1 — product companies, GCCs, Big 4 (JobSpy)
    "naukri",     # Tier 1 — volume leader for Indian IT/data roles (JobSpy)
    "google",     # Tier 2 — aggregates postings missed by LinkedIn/Naukri (JobSpy)
    "cutshort",   # Tier 2 — skill-based matching, AI startups (custom scraper)
]

KEYWORDS = [
    "data engineer",
    "ML engineer",
    "AI engineer",
    "GenAI engineer",
    "data scientist",
    "machine learning engineer",
]

LOCATIONS = ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Remote India"]

MIN_FIT_SCORE = 70           # LLM fit score gate — jobs below this are skipped
KEYWORD_PRESCORE_MIN = 0.12  # cheap string-match gate before the LLM is called
                             # fraction of CANDIDATE_SKILLS that must appear in JD
                             # 0.12 = 12% → ~8 of 68 skills must appear
                             # calibrated: ML/DE JDs score ~21%, DA ~13%, trainer/IT ~6-9%

# ── Job search config (consumed by scrapers) ───────────────────────────────
JOB_SEARCH = {
    "keywords":         KEYWORDS,
    "location":         LOCATIONS[0],   # primary location for single-location scrapers
    "locations":        LOCATIONS,      # full list for multi-location scrapes
    "max_per_platform": 10,
    "hours_old":        72,
}

# ── Approved / hand-crafted resumes ────────────────────────────────────────
APPROVED_RESUMES_DIR = "resumes"   # drop <cluster>.txt here to override AI output

# How the pipeline selects a resume for each job:
#   "prefer_approved" — use resumes/<cluster>.txt if present, else cached, else generate
#   "generate"        — always run LLM tailor (ignore both approved and cache)
#   "approved_only"   — skip job entirely if no approved resume exists for its cluster
RESUME_MODE = "prefer_approved"

CLUSTER_CACHE_DAYS = 7

ROLE_CLUSTERS = {
    "ml_ai": {
        "label": "ML / AI Engineer",
        "keywords": [
            "data scientist", "machine learning engineer", "ml engineer",
            "ai engineer", "nlp engineer", "deep learning engineer",
            "applied scientist", "research scientist",
        ],
    },
    "data_engineering": {
        "label": "Data Engineer",
        "keywords": [
            "data engineer", "big data engineer", "analytics engineer",
            "etl engineer", "platform engineer",
        ],
    },
    "analytics_bi": {
        "label": "Analytics / BI",
        "keywords": [
            "business intelligence engineer", "data analyst", "bi engineer",
            "business analyst", "reporting analyst",
        ],
    },
    "entry_ds": {
        "label": "Entry-level Data Scientist",
        "keywords": [
            "associate data scientist", "junior data scientist",
            "junior ml", "entry level data",
        ],
    },
    "python_dev": {
        "label": "Python Developer (DS)",
        "keywords": [
            "python developer data science", "python developer",
            "software engineer data", "backend data",
        ],
    },
}

# ── Thresholds ─────────────────────────────────────────────────────────────
FIT_SCORE_THRESHOLD   = MIN_FIT_SCORE  # alias used throughout pipeline
RESUME_SIMILARITY_MIN = 70            # skip if tailored resume quality drops below this

# ── Active platforms (derived from JOB_BOARDS) ─────────────────────────────
PLATFORMS = {b: True for b in JOB_BOARDS}

# ── Auto-apply ─────────────────────────────────────────────────────────────
HEADLESS = False  # set True after sessions are saved

# ── Login credentials (loaded from _local.py, never committed) ─────────────
LOGIN_EMAIL    = _SECRETS_EMAIL    or os.getenv("APPLY_EMAIL",    "")
LOGIN_PASSWORD = _SECRETS_PASSWORD or os.getenv("APPLY_PASSWORD", "")

LINKEDIN_EMAIL    = _SECRETS_LI_EMAIL    or os.getenv("LINKEDIN_EMAIL",    LOGIN_EMAIL)
LINKEDIN_PASSWORD = _SECRETS_LI_PASSWORD or os.getenv("LINKEDIN_PASSWORD", LOGIN_PASSWORD)
INDEED_EMAIL      = _SECRETS_IN_EMAIL    or os.getenv("INDEED_EMAIL",      LOGIN_EMAIL)
INDEED_PASSWORD   = _SECRETS_IN_PASSWORD or os.getenv("INDEED_PASSWORD",   LOGIN_PASSWORD)

CREDENTIALS: dict = {}

# ── Output ─────────────────────────────────────────────────────────────────
DB_PATH    = "output/applications.db"
OUTPUT_DIR = "output/applications"
# AI mode: "groq" (API, rate limited) or "ollama" (local, unlimited)
AI_MODE = "ollama"

# ── Applicant profile (used by auto-apply bots to fill forms) ──────────────
PROFILE = {
    "first_name":        "Navaneeta",
    "last_name":         "Padmakumar",
    "full_name":         "Navaneeta Padmakumar",
    "email":             os.getenv("APPLY_EMAIL",    "nxp230016@utdallas.edu"),
    "phone":             os.getenv("APPLY_PHONE",    "+19453389465"),
    "city":              "Richardson",
    "state":             "Texas",
    "country":           "United States",
    "linkedin_url":      "https://linkedin.com/in/navaneetapk",
    "github_url":        "https://github.com/nxp0999",
    "current_company":   "Datanimbus Technologies",
    "years_experience":  "4",
    "notice_period":     "Immediate",
    "salary_expected":   "Negotiable",
    "work_authorization": "Yes",
    "visa_sponsorship":  "No",   # overridden per-job: "Yes" if job is outside India
    "us_citizen":        "No",
    "willing_to_relocate": "Yes",
}
