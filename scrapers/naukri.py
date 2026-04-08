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
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _make_job_id(title, company, url):
    return "naukri_" + hashlib.md5(f"{title}_{company}_{url}".encode()).hexdigest()[:12]


def scrape(max_jobs=None):
    max_jobs = max_jobs or JOB_SEARCH["max_per_platform"]
    jobs = []

    for keyword in JOB_SEARCH["keywords"][:3]:
        if len(jobs) >= max_jobs:
            break

        kw = keyword.lower().replace(" ", "-")
        url = f"https://www.naukri.com/{kw}-jobs-in-india"

        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            cards = soup.find_all("article", {"class": "jobTuple"})
            if not cards:
                cards = soup.find_all("div", {"class": "srp-jobtuple-wrapper"})

            for card in cards:
                if len(jobs) >= max_jobs:
                    break

                title_el   = card.find("a", {"class": "title"})
                company_el = card.find("a", {"class": "subTitle"})
                loc_el     = card.find("li", {"class": "location"})

                title   = title_el.get_text(strip=True)   if title_el   else "Unknown"
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                loc     = loc_el.get_text(strip=True)     if loc_el     else "India"
                job_url = title_el["href"]                if title_el and title_el.get("href") else ""

                jobs.append({
                    "platform":    "naukri",
                    "job_id":      _make_job_id(title, company, job_url),
                    "title":       title,
                    "company":     company,
                    "location":    loc,
                    "apply_url":   job_url,
                    "description": "",  # Naukri requires login for full JD
                })
                time.sleep(0.5)

        except Exception as e:
            print(f"[Naukri] Error on '{keyword}': {e}")

    print(f"[Naukri] Scraped {len(jobs)} jobs.")
    return jobs