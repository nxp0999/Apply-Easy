"""
pipeline/apply_detector.py
Classifies each scraped job as 'easy', 'full_form', or 'unknown'.

  easy       — the platform handles the full apply flow in-page
               (LinkedIn Easy Apply, Indeed Apply)
  full_form  — clicking Apply opens the company's own careers site
  unknown    — couldn't determine without visiting the page

Detection priority:
  1. jobspy's easy_apply boolean   (LinkedIn — no extra request needed)
  2. job_url_direct domain check   (Indeed + LinkedIn — no extra request)
  3. HTTP page check               (fallback, one GET per job)
"""

import re
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# Domains that indicate the job stays on the platform (easy apply)
_PLATFORM_DOMAINS = {
    "linkedin": "linkedin.com",
    "indeed":   "indeed.com",
    "naukri":   "naukri.com",
    "internshala": "internshala.com",
}

# Domains that are definitely external company sites
_EXTERNAL_HINTS = re.compile(
    r"(greenhouse\.io|lever\.co|workday\.com|taleo\.net|icims\.com"
    r"|myworkdayjobs\.com|smartrecruiters\.com|ashbyhq\.com"
    r"|bamboohr\.com|jobvite\.com|recruitee\.com|careers\.\w+\.com)",
    re.IGNORECASE,
)


def _domain_of(url: str) -> str:
    m = re.search(r"https?://([^/]+)", url)
    return m.group(1).lower() if m else ""


def _is_external(url: str, platform: str) -> bool:
    """True if url clearly points away from the platform."""
    if not url or url in ("None", "nan"):
        return False
    domain = _domain_of(url)
    platform_domain = _PLATFORM_DOMAINS.get(platform, "")
    if platform_domain and platform_domain in domain:
        return False          # still on the platform
    if _EXTERNAL_HINTS.search(url):
        return True           # well-known ATS
    if platform_domain and platform_domain not in domain and domain:
        return True           # different domain altogether
    return False


def _http_check_linkedin(url: str) -> str:
    """GET the LinkedIn job page and look for the Easy Apply button."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if "Easy Apply" in r.text:
            return "easy"
        if "Apply" in r.text:
            return "full_form"
    except Exception:
        pass
    return "unknown"


def _http_check_indeed(url: str) -> str:
    """Indeed Easy Apply URLs stay on indeed.com or contain 'indeedapply'."""
    if "indeedapply" in url or "/apply/" in url:
        return "easy"
    try:
        # Follow the redirect and check where we land
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        final = r.url
        if "indeed.com" in _domain_of(final):
            return "easy"
        return "full_form"
    except Exception:
        pass
    return "unknown"


def classify(job: dict) -> str:
    """
    Returns 'easy', 'full_form', or 'unknown'.

    Pass the full job dict as stored/scraped — uses every available signal
    before falling back to a live HTTP check.
    """
    platform    = job.get("platform", "").lower()
    apply_url   = str(job.get("apply_url") or "")
    direct_url  = str(job.get("apply_url_direct") or "")
    easy_apply  = job.get("easy_apply")   # True / False / None (jobspy field)

    # ── Signal 1: jobspy easy_apply boolean (most reliable for LinkedIn) ───
    if easy_apply is True:
        return "easy"
    if easy_apply is False:
        # Could still be on the platform with an external redirect; use
        # direct URL to confirm rather than blindly returning full_form.
        if direct_url and _is_external(direct_url, platform):
            return "full_form"
        # easy_apply=False on LinkedIn means they link out
        if platform == "linkedin":
            return "full_form"

    # ── Signal 2: job_url_direct domain check (Indeed + others) ───────────
    if direct_url and direct_url not in ("None", "nan", ""):
        if _is_external(direct_url, platform):
            return "full_form"
        # Direct URL stays on the platform
        platform_domain = _PLATFORM_DOMAINS.get(platform, "")
        if platform_domain and platform_domain in _domain_of(direct_url):
            return "easy"

    # ── Signal 3: apply_url itself ─────────────────────────────────────────
    if _is_external(apply_url, platform):
        return "full_form"

    # ── Signal 4: HTTP fallback (one GET per job) ──────────────────────────
    if not apply_url:
        return "unknown"
    if platform == "linkedin":
        return _http_check_linkedin(apply_url)
    if platform == "indeed":
        return _http_check_indeed(apply_url)

    return "unknown"


def classify_batch(jobs: list, console=None) -> dict:
    """
    Classify a list of job dicts.
    Returns {job_id: apply_type} mapping.
    """
    results = {}
    for job in jobs:
        jid = job["job_id"]
        apply_type = classify(job)
        results[jid] = apply_type
        if console:
            color = {"easy": "green", "full_form": "yellow", "unknown": "dim"}.get(apply_type, "white")
            console.print(
                f"  [{color}]{apply_type:10}[/{color}]  "
                f"{job.get('title', '')[:35]:35}  {job.get('company', '')[:20]}"
            )
    return results
