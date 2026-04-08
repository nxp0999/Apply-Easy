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
    return "internshala_" + hashlib.md5(url.encode()).hexdigest()[:12]


def _get_description(job_url):
    try:
        r = requests.get(job_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        desc = soup.find("div", {"class": "internship_details"})
        return desc.get_text(separator="\n").strip() if desc else ""
    except Exception:
        return ""


def scrape(max_jobs=None):
    max_jobs = max_jobs or JOB_SEARCH["max_per_platform"]
    jobs = []

    for keyword in JOB_SEARCH["keywords"][:3]:
        if len(jobs) >= max_jobs:
            break

        kw = keyword.lower().replace(" ", "-")
        url = f"https://internshala.com/jobs/{kw}-jobs"

        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"class": "individual_internship"})

            for card in cards:
                if len(jobs) >= max_jobs:
                    break

                title_el   = card.find("h3", {"class": "job-internship-name"})
                company_el = card.find("p",  {"class": "company-name"})
                link_el    = card.find("a",  href=True)

                title   = title_el.get_text(strip=True)   if title_el   else "Unknown"
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                href    = link_el["href"]                 if link_el    else ""
                job_url = f"https://internshala.com{href}" if href.startswith("/") else href

                description = _get_description(job_url) if job_url else ""

                jobs.append({
                    "platform":    "internshala",
                    "job_id":      _make_job_id(job_url),
                    "title":       title,
                    "company":     company,
                    "location":    "India",
                    "apply_url":   job_url,
                    "description": description,
                })
                time.sleep(1)

        except Exception as e:
            print(f"[Internshala] Error on '{keyword}': {e}")

    print(f"[Internshala] Scraped {len(jobs)} jobs.")
    return jobs