import hashlib
from jobspy import scrape_jobs
from config import JOB_SEARCH


def _make_job_id(platform, url):
    return f"{platform}_" + hashlib.md5(url.encode()).hexdigest()[:12]


def scrape_all(max_jobs=None):
    max_jobs  = max_jobs or JOB_SEARCH["max_per_platform"]
    hours_old = JOB_SEARCH.get("hours_old", 72)
    all_jobs  = []

    for keyword in JOB_SEARCH["keywords"][:5]:
        print(f"\n[Scraper] Searching: '{keyword}' (last {hours_old}h)")
        try:
            df = scrape_jobs(
                site_name=["indeed", "linkedin"],
                search_term=keyword,
                location=JOB_SEARCH.get("location", "India"),
                results_wanted=max_jobs,
                hours_old=hours_old,
                country_indeed="India",
            )

            if df is None or df.empty:
                print(f"  No results for '{keyword}'")
                continue

            for _, row in df.iterrows():
                url         = str(row.get("job_url") or "")
                url_direct  = str(row.get("job_url_direct") or "")
                platform    = "linkedin" if "linkedin.com" in url else "indeed"
                title       = str(row.get("title") or "Unknown")
                company     = str(row.get("company") or "Unknown")
                location    = str(row.get("location") or "India")
                description = str(row.get("description") or "")
                easy_apply  = row.get("easy_apply")
                # Capture posting date — jobspy returns datetime or None
                raw_date    = row.get("date_posted")
                date_posted = (
                    raw_date.strftime("%Y-%m-%d")
                    if raw_date is not None and not (isinstance(raw_date, float))
                    else None
                )

                all_jobs.append({
                    "platform":         platform,
                    "job_id":           _make_job_id(platform, url),
                    "title":            title,
                    "company":          company,
                    "location":         location,
                    "apply_url":        url,
                    "apply_url_direct": url_direct,
                    "description":      description,
                    "easy_apply":       easy_apply,
                    "date_posted":      date_posted,
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