"""
scrapers/ats_scraper.py

Scrapes job listings directly from Greenhouse, Ashby, and Lever ATS APIs
for pre-configured Indian tech/AI/ML companies.

Returns job dicts in the same format as jobspy_scraper.py so the rest of
the pipeline (insert_job, filters, scoring) is unchanged.

No credentials needed — all three APIs are public.
"""

import requests
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup

_TIMEOUT = 10  # seconds per request

# ── Company registry ──────────────────────────────────────────────────────────
# Format: { "ats": "greenhouse|ashby|lever", "slug": "<api-slug>", "name": "<display name>" }
# Only include companies with a significant India presence (Bengaluru / Hyderabad / Pune / Remote)
PORTAL_COMPANIES = [
    # Greenhouse
    {"ats": "greenhouse", "slug": "flipkart",         "name": "Flipkart"},
    {"ats": "greenhouse", "slug": "phonepe",           "name": "PhonePe"},
    {"ats": "greenhouse", "slug": "swiggy",            "name": "Swiggy"},
    {"ats": "greenhouse", "slug": "walmart",           "name": "Walmart Global Tech"},
    {"ats": "greenhouse", "slug": "uber",              "name": "Uber"},
    {"ats": "greenhouse", "slug": "atlassian",         "name": "Atlassian"},
    {"ats": "greenhouse", "slug": "confluent",         "name": "Confluent"},
    {"ats": "greenhouse", "slug": "databricks",        "name": "Databricks"},
    {"ats": "greenhouse", "slug": "niyo",              "name": "Niyo"},
    {"ats": "greenhouse", "slug": "meesho",            "name": "Meesho"},
    # Ashby
    {"ats": "ashby",      "slug": "setu",              "name": "Setu"},
    {"ats": "ashby",      "slug": "juspay",            "name": "Juspay"},
    {"ats": "ashby",      "slug": "moneyforward",      "name": "Money Forward"},
    {"ats": "ashby",      "slug": "hasura",            "name": "Hasura"},
    {"ats": "ashby",      "slug": "browserstack",      "name": "BrowserStack"},
    {"ats": "ashby",      "slug": "razorpay",          "name": "Razorpay"},
    # NOTE: MoEngage, CleverTap, Sprinklr, Sarvam AI, BCG X, Adobe
    # do not expose public Greenhouse/Ashby/Lever APIs.
    # They post on LinkedIn — covered by JobSpy scraper.
    # Lever
    {"ats": "lever",      "slug": "zomato",            "name": "Zomato"},
    {"ats": "lever",      "slug": "zepto",             "name": "Zepto"},
    {"ats": "lever",      "slug": "groww",             "name": "Groww"},
    {"ats": "lever",      "slug": "postman",           "name": "Postman"},
    {"ats": "lever",      "slug": "chargebee",         "name": "Chargebee"},
    {"ats": "lever",      "slug": "freshworks",        "name": "Freshworks"},
]

# Keywords to keep — only return jobs with at least one of these in title/dept
_RELEVANT_TITLE_KEYWORDS = [
    "data", "machine learning", "ml", "ai", "analytics", "engineer",
    "scientist", "python", "backend", "platform", "nlp", "llm",
    "software", "applied", "research",
]

_INDIA_LOCS = re.compile(
    r"india|bangalore|bengaluru|hyderabad|pune|mumbai|delhi|noida|"
    r"remote|hybrid|pan.india|karnataka|anywhere",
    re.IGNORECASE,
)


def _strip_html(raw: str) -> str:
    """Convert HTML job description to plain text."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    return soup.get_text(separator="\n").strip()


def _is_relevant(title: str, dept: str = "") -> bool:
    combined = (title + " " + dept).lower()
    return any(kw in combined for kw in _RELEVANT_TITLE_KEYWORDS)


def _is_india_or_remote(location: str) -> bool:
    return bool(_INDIA_LOCS.search(location))


def _parse_date(raw) -> str | None:
    """Normalize epoch ms or ISO string to YYYY-MM-DD."""
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            # Greenhouse/Lever use epoch milliseconds
            dt = datetime.fromtimestamp(raw / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


# ── Greenhouse ────────────────────────────────────────────────────────────────

def _scrape_greenhouse(slug: str, company_name: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    jobs = []
    for item in data.get("jobs", []):
        title    = item.get("title", "")
        dept     = (item.get("departments") or [{}])[0].get("name", "")
        location = (item.get("location") or {}).get("name", "")
        content  = item.get("content", "") or ""

        if not _is_relevant(title, dept):
            continue
        if location and not _is_india_or_remote(location):
            continue

        jobs.append({
            "platform":        "ats-greenhouse",
            "job_id":          f"gh-{item['id']}",
            "title":           title,
            "company":         company_name,
            "location":        location,
            "description":     _strip_html(content),
            "apply_url":       item.get("absolute_url", ""),
            "apply_url_direct":item.get("absolute_url", ""),
            "date_posted":     _parse_date(item.get("updated_at")),
            "salary_min":      None,
            "salary_max":      None,
        })
    return jobs


# ── Ashby ─────────────────────────────────────────────────────────────────────

def _scrape_ashby(slug: str, company_name: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    jobs = []
    for item in data.get("jobPostings", []):
        title    = item.get("title", "")
        dept     = item.get("departmentName", "")
        location = item.get("locationName", "") or item.get("location", "")
        body     = item.get("descriptionHtml", "") or item.get("description", "")

        if not _is_relevant(title, dept):
            continue
        if location and not _is_india_or_remote(location):
            continue

        jobs.append({
            "platform":        "ats-ashby",
            "job_id":          f"ashby-{item.get('id', item.get('jobId', ''))}",
            "title":           title,
            "company":         company_name,
            "location":        location,
            "description":     _strip_html(body),
            "apply_url":       item.get("jobUrl", ""),
            "apply_url_direct":item.get("applyUrl", item.get("jobUrl", "")),
            "date_posted":     _parse_date(item.get("updatedAt") or item.get("publishedAt")),
            "salary_min":      None,
            "salary_max":      None,
        })
    return jobs


# ── Lever ─────────────────────────────────────────────────────────────────────

def _scrape_lever(slug: str, company_name: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    jobs = []
    for item in data:
        title    = item.get("text", "")
        dept     = (item.get("categories") or {}).get("department", "")
        location = (item.get("categories") or {}).get("location", "") or \
                   (item.get("workplaceType", ""))

        # Build description from Lever's list-based content
        lists = item.get("lists", [])
        desc_parts = [item.get("descriptionPlain", "")]
        for lst in lists:
            desc_parts.append(lst.get("text", "") + "\n")
            desc_parts.append(_strip_html(lst.get("content", "")))
        description = "\n".join(p for p in desc_parts if p)

        if not _is_relevant(title, dept):
            continue
        if location and not _is_india_or_remote(location):
            continue

        apply_url = f"https://jobs.lever.co/{slug}/{item.get('id', '')}/apply"
        jobs.append({
            "platform":        "ats-lever",
            "job_id":          f"lever-{item.get('id', '')}",
            "title":           title,
            "company":         company_name,
            "location":        location,
            "description":     description,
            "apply_url":       item.get("hostedUrl", apply_url),
            "apply_url_direct":apply_url,
            "date_posted":     _parse_date(item.get("createdAt")),
            "salary_min":      None,
            "salary_max":      None,
        })
    return jobs


# ── Public API ─────────────────────────────────────────────────────────────────

_SCRAPERS = {
    "greenhouse": _scrape_greenhouse,
    "ashby":      _scrape_ashby,
    "lever":      _scrape_lever,
}


def scrape_ats_portals(companies: list[dict] | None = None) -> list[dict]:
    """
    Scrape all configured ATS portals.
    Returns a flat list of job dicts compatible with insert_job().
    """
    targets  = companies or PORTAL_COMPANIES
    all_jobs: list[dict] = []

    for co in targets:
        ats    = co["ats"]
        slug   = co["slug"]
        name   = co["name"]
        fn     = _SCRAPERS.get(ats)
        if fn is None:
            continue
        try:
            jobs = fn(slug, name)
            all_jobs.extend(jobs)
        except Exception:
            pass  # one company failing shouldn't stop the rest

    return all_jobs
