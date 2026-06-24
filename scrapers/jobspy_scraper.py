import hashlib
from jobspy import scrape_jobs
from config import JOB_SEARCH, JOB_BOARDS

# JobSpy-supported platforms only (wellfound/cutshort use separate scrapers)
_JOBSPY_SUPPORTED = {"linkedin", "naukri", "google", "glassdoor"}
_ACTIVE_PLATFORMS  = [p for p in JOB_BOARDS if p in _JOBSPY_SUPPORTED] or ["linkedin", "naukri"]


def _make_job_id(platform, url):
    return f"{platform}_" + hashlib.md5(url.encode()).hexdigest()[:12]


def scrape_all(max_jobs=None):
    max_jobs  = max_jobs or JOB_SEARCH["max_per_platform"]
    hours_old = JOB_SEARCH.get("hours_old", 72)
    all_jobs  = []

    for keyword in JOB_SEARCH["keywords"][:5]:
        print(f"\n[Scraper] Searching: '{keyword}' on {_ACTIVE_PLATFORMS} (last {hours_old}h)")
        try:
            df = scrape_jobs(
                site_name=_ACTIVE_PLATFORMS,
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
                if "linkedin.com" in url:
                    platform = "linkedin"
                elif "naukri.com" in url:
                    platform = "naukri"
                elif "google.com/search" in url or "google.com/jobs" in url:
                    platform = "google"
                else:
                    platform = str(row.get("site") or "unknown")
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
                # Capture salary range when available
                def _safe_num(v):
                    try:
                        f = float(v)
                        return int(f) if f == f else None  # NaN check
                    except (TypeError, ValueError):
                        return None
                salary_min = _safe_num(row.get("min_amount"))
                salary_max = _safe_num(row.get("max_amount"))

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
                    "salary_min":       salary_min,
                    "salary_max":       salary_max,
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