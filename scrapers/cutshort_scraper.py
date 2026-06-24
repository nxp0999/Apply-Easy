"""
scrapers/cutshort_scraper.py

Scrapes job listings from Cutshort.io via their public search API.
Cutshort uses skill-based matching — strong for AI/ML startup roles in India.

No credentials required. Returns jobs in the same dict format as jobspy_scraper.
"""

import hashlib
import requests
import logging
from config import JOB_SEARCH

logger = logging.getLogger(__name__)

_TIMEOUT  = 12
_BASE_URL = "https://cutshort.io/api/public/jobs/search"

_SKILL_MAP = {
    "data engineer":           ["PySpark", "Apache Kafka", "Databricks", "Python", "SQL", "ETL"],
    "ml engineer":             ["PyTorch", "TensorFlow", "Python", "Machine Learning", "MLOps"],
    "ai engineer":             ["LLM", "Python", "NLP", "Generative AI", "RAG", "LangChain"],
    "genai engineer":          ["LLM", "LangChain", "RAG", "Generative AI", "Python", "Vector DB"],
    "data scientist":          ["Python", "Machine Learning", "Statistics", "SQL", "Deep Learning"],
    "machine learning engineer": ["Python", "PyTorch", "Scikit-learn", "MLOps", "Kubeflow"],
    "software engineer":       ["Python", "System Design", "Backend", "APIs"],
    "backend engineer":        ["Python", "FastAPI", "Django", "PostgreSQL", "Redis"],
}


def _make_job_id(url: str) -> str:
    return "cutshort_" + hashlib.md5(url.encode()).hexdigest()[:12]


def _skills_for_keyword(keyword: str) -> list[str]:
    return _SKILL_MAP.get(keyword.lower(), ["Python", "Machine Learning", "Data"])


def scrape_cutshort(max_jobs: int | None = None) -> list[dict]:
    max_jobs  = max_jobs or JOB_SEARCH.get("max_per_platform", 20)
    keywords  = JOB_SEARCH.get("keywords", ["data engineer"])[:5]
    location  = "Bangalore"  # Cutshort is Bangalore-centric
    all_jobs: list[dict] = []
    seen: set[str] = set()

    for keyword in keywords:
        skills = _skills_for_keyword(keyword)
        payload = {
            "query":    keyword,
            "skills":   skills[:4],
            "location": location,
            "size":     min(max_jobs, 50),
            "from":     0,
        }
        try:
            r = requests.post(_BASE_URL, json=payload, timeout=_TIMEOUT)
            if r.status_code != 200:
                logger.warning(f"[Cutshort] {r.status_code} for '{keyword}' — skipping")
                continue

            data = r.json()
            jobs_raw = data.get("data", data.get("jobs", []))
            if not isinstance(jobs_raw, list):
                continue

            for job in jobs_raw:
                url = job.get("url") or job.get("job_url") or ""
                if not url:
                    slug = job.get("slug") or job.get("id") or ""
                    url  = f"https://cutshort.io/job/{slug}" if slug else ""
                if not url:
                    continue

                job_id = _make_job_id(url)
                if job_id in seen:
                    continue
                seen.add(job_id)

                title       = job.get("title") or job.get("designation") or "Unknown"
                company_obj = job.get("company") or {}
                company     = (company_obj.get("name") if isinstance(company_obj, dict)
                               else str(company_obj)) or "Unknown"
                description = job.get("description") or job.get("requirements") or ""
                loc         = job.get("location") or location
                sal_min     = job.get("salary_min") or job.get("min_salary")
                sal_max     = job.get("salary_max") or job.get("max_salary")
                date_posted = job.get("created_at") or job.get("posted_at")
                if date_posted and len(str(date_posted)) > 10:
                    date_posted = str(date_posted)[:10]

                all_jobs.append({
                    "platform":         "cutshort",
                    "job_id":           job_id,
                    "title":            title,
                    "company":          company,
                    "location":         str(loc),
                    "apply_url":        url,
                    "apply_url_direct": url,
                    "description":      description,
                    "easy_apply":       False,
                    "date_posted":      date_posted,
                    "salary_min":       sal_min,
                    "salary_max":       sal_max,
                })

        except Exception as e:
            logger.warning(f"[Cutshort] Error for '{keyword}': {e}")

    logger.info(f"[Cutshort] Scraped {len(all_jobs)} unique jobs")
    return all_jobs
