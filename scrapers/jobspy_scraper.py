import hashlib
import pandas as pd
from jobspy import scrape_jobs
from config import JOB_SEARCH


def _make_job_id(platform, url):
    return f"{platform}_" + hashlib.md5(url.encode()).hexdigest()[:12]


def scrape_all(max_jobs=None):
    max_jobs = max_jobs or JOB_SEARCH["max_per_platform"]
    all_jobs = []

    for keyword in JOB_SEARCH["keywords"][:5]:
        print(f"\n[Scraper] Searching: '{keyword}'")
        try:
            df = scrape_jobs(
                site_name=["indeed", "linkedin"],
                search_term=keyword,
                location=JOB_SEARCH.get("location", "India"),
                results_wanted=max_jobs,
                country_indeed="India",
            )

            if df is None or df.empty:
                print(f"  No results for '{keyword}'")
                continue

            for _, row in df.iterrows():
                url      = str(row.get("job_url") or "")
                platform = "linkedin" if "linkedin.com" in url else "indeed"
                title    = str(row.get("title") or "Unknown")
                company  = str(row.get("company") or "Unknown")
                location = str(row.get("location") or "India")
                description = str(row.get("description") or "")

                all_jobs.append({
                    "platform":    platform,
                    "job_id":      _make_job_id(platform, url),
                    "title":       title,
                    "company":     company,
                    "location":    location,
                    "apply_url":   url,
                    "description": description,
                })

        except Exception as e:
            print(f"  [Scraper] Error on '{keyword}': {e}")

    # Deduplicate by job_id
    seen = set()
    unique = []
    for j in all_jobs:
        if j["job_id"] not in seen:
            seen.add(j["job_id"])
            unique.append(j)

    print(f"\n[Scraper] Total unique jobs scraped: {len(unique)}")
    return unique