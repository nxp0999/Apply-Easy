import requests
from bs4 import BeautifulSoup
import hashlib
import time
from config import JOB_SEARCH

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def _make_job_id(url):
    return "linkedin_" + hashlib.md5(url.encode()).hexdigest()[:12]


def _get_description(job_url):
    try:
        r = requests.get(job_url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        desc = soup.find("div", {"class": "show-more-less-html__markup"})
        return desc.get_text(separator="\n").strip() if desc else ""
    except Exception:
        return ""


def scrape(max_jobs=None):
    max_jobs = max_jobs or JOB_SEARCH["max_per_platform"]
    jobs = []

    for keyword in JOB_SEARCH["keywords"][:3]:
        if len(jobs) >= max_jobs:
            break

        params = {
            "keywords": keyword,
            "location": JOB_SEARCH.get("location", "India"),
            "f_TPR":    "r604800",
            "start":    0,
        }

        try:
            r = requests.get(
                "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                params=params, headers=HEADERS, timeout=15
            )
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"class": "base-card"})

            for card in cards:
                if len(jobs) >= max_jobs:
                    break

                title_el   = card.find("h3", {"class": "base-search-card__title"})
                company_el = card.find("h4", {"class": "base-search-card__subtitle"})
                loc_el     = card.find("span", {"class": "job-search-card__location"})
                link_el    = card.find("a", {"class": "base-card__full-link"})

                title   = title_el.get_text(strip=True)           if title_el   else "Unknown"
                company = company_el.get_text(strip=True)         if company_el else "Unknown"
                loc     = loc_el.get_text(strip=True)             if loc_el     else ""
                job_url = link_el["href"].split("?")[0]           if link_el    else ""

                description = _get_description(job_url) if job_url else ""

                jobs.append({
                    "platform":    "linkedin",
                    "job_id":      _make_job_id(job_url),
                    "title":       title,
                    "company":     company,
                    "location":    loc,
                    "apply_url":   job_url,
                    "description": description,
                })
                time.sleep(1.5)

        except Exception as e:
            print(f"[LinkedIn] Error on '{keyword}': {e}")

    print(f"[LinkedIn] Scraped {len(jobs)} jobs.")
    return jobs