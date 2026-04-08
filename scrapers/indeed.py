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


def _make_job_id(title, company, url):
    return "indeed_" + hashlib.md5(f"{title}_{company}_{url}".encode()).hexdigest()[:12]


def _get_description(job_url):
    try:
        r = requests.get(job_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        desc = soup.find("div", {"id": "jobDescriptionText"})
        return desc.get_text(separator="\n").strip() if desc else ""
    except Exception:
        return ""


def scrape(max_jobs=None):
    max_jobs = max_jobs or JOB_SEARCH["max_per_platform"]
    jobs = []

    for keyword in JOB_SEARCH["keywords"][:3]:  # limit to first 3 keywords
        if len(jobs) >= max_jobs:
            break

        params = {
            "q": keyword,
            "l": JOB_SEARCH.get("location", "India"),
            "start": 0,
        }

        try:
            r = requests.get(
                "https://in.indeed.com/jobs",
                params=params, headers=HEADERS, timeout=15
            )
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", class_="job_seen_beacon")

            for card in cards:
                if len(jobs) >= max_jobs:
                    break

                title_el   = card.find("span", {"id": lambda x: x and "jobTitle" in x})
                company_el = card.find("span", {"data-testid": "company-name"})
                loc_el     = card.find("div", {"data-testid": "text-location"})
                link_el    = card.find("a", href=True)

                title   = title_el.get_text(strip=True)   if title_el   else "Unknown"
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                loc     = loc_el.get_text(strip=True)     if loc_el     else ""
                href    = link_el["href"]                 if link_el    else ""
                job_url = f"https://in.indeed.com{href}" if href.startswith("/") else href

                description = _get_description(job_url)

                jobs.append({
                    "platform":    "indeed",
                    "job_id":      _make_job_id(title, company, job_url),
                    "title":       title,
                    "company":     company,
                    "location":    loc,
                    "apply_url":   job_url,
                    "description": description,
                })
                time.sleep(1)

        except Exception as e:
            print(f"[Indeed] Error on '{keyword}': {e}")

    print(f"[Indeed] Scraped {len(jobs)} jobs.")
    return jobs