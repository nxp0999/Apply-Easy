import argparse
import atexit
import json
import logging
import os
import sys
from rich.console import Console
from rich.table import Table
from rich.progress import track
import shutil
import re

from config import (
    AI_MODE,
    BASE_RESUME,
    FIT_SCORE_THRESHOLD,
    GROQ_API_KEY,
    JOB_BOARDS,
    KEYWORD_PRESCORE_MIN,
    RESUME_MODE,
    RESUME_SIMILARITY_MIN,
    OUTPUT_DIR,
    ROLE_CLUSTERS,
)
from filters import (
    is_blacklisted, is_overleveled, is_off_target_title,
    is_wrong_location, keyword_prescore,
    is_stale_posting, is_ghost_job,
)
from db import (
    init_db,
    migrate_db,
    insert_job,
    update_claude_outputs,
    mark_applied,
    get_all,
    get_unclassified,
    set_apply_type,
    get_easy_apply_pending,
    get_full_form_pending,
)

console = Console()

_LOCK_PATH = "output/pipeline.lock"


def _acquire_lock():
    """Prevent two pipeline runs from overlapping (safe for cron)."""
    os.makedirs("output", exist_ok=True)
    if os.path.exists(_LOCK_PATH):
        with open(_LOCK_PATH) as f:
            pid = f.read().strip()
        try:
            os.kill(int(pid), 0)  # signal 0 = check existence only
            console.print(f"[red]Pipeline already running (PID {pid}). Exiting.[/red]")
            sys.exit(0)
        except (ProcessLookupError, ValueError, OSError):
            pass  # stale lock from a crashed run — continue
    with open(_LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(_LOCK_PATH) and os.remove(_LOCK_PATH))


def _setup_logging():
    """Write key pipeline events to output/run.log (survives cron redirects)."""
    os.makedirs("output", exist_ok=True)
    logging.basicConfig(
        filename="output/run.log",
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("=== Pipeline started ===")
    atexit.register(lambda: logging.info("=== Pipeline finished ==="))


# ── STEP 1: SCRAPE ────────────────────────────────────────────────────────


def scrape_all():
    from scrapers.jobspy_scraper import scrape_all as _scrape
    from scrapers.ats_scraper import scrape_ats_portals

    jobspy_jobs    = _scrape()
    ats_jobs       = scrape_ats_portals()
    cutshort_jobs: list = []

    if "cutshort" in JOB_BOARDS:
        from scrapers.cutshort_scraper import scrape_cutshort
        cutshort_jobs = scrape_cutshort()

    all_jobs = jobspy_jobs + ats_jobs + cutshort_jobs

    for job in all_jobs:
        insert_job(job)

    console.print(
        f"\n[green]✓ Scraped {len(all_jobs)} unique jobs[/green]  "
        f"[dim](JobSpy: {len(jobspy_jobs)}, ATS portals: {len(ats_jobs)}, Cutshort: {len(cutshort_jobs)})[/dim]"
    )
    return all_jobs


# ── STEP 2: CLASSIFY APPLY TYPE ───────────────────────────────────────────


def classify_jobs():
    """Detect easy-apply vs full-form for all unclassified jobs."""
    from pipeline.apply_detector import classify_batch

    jobs = get_unclassified()
    if not jobs:
        console.print("[yellow]No unclassified jobs.[/yellow]")
        return

    console.print(f"\n[cyan]Classifying {len(jobs)} jobs...[/cyan]\n")
    results = classify_batch(jobs, console=console)

    for job_id, apply_type in results.items():
        # Find the job to get apply_url_direct for storage
        job = next((j for j in jobs if j["job_id"] == job_id), {})
        set_apply_type(job_id, apply_type, job.get("apply_url_direct", ""))

    easy      = sum(1 for t in results.values() if t == "easy")
    full_form = sum(1 for t in results.values() if t == "full_form")
    unknown   = sum(1 for t in results.values() if t == "unknown")
    console.print(
        f"\n[green]Easy apply: {easy}[/green]  |  "
        f"[yellow]Full form: {full_form}[/yellow]  |  "
        f"[dim]Unknown: {unknown}[/dim]"
    )
    logging.info(f"Classified {len(results)} jobs — easy:{easy} full:{full_form} unknown:{unknown}")


def _clean_model_output(text: str) -> str:
    """Strip artefacts that local models (Mistral etc.) inject into resume text."""
    # Remove AI preamble lines
    text = re.sub(
        r"^(Here'?s?.*?:|Sure[,!].*?:|The (corrected|tailored|updated|revised).*?:)\s*\n",
        "", text, flags=re.IGNORECASE,
    ).strip()
    # Remove "(Action Verb: X)" labels Mistral adds when following prompt examples
    text = re.sub(r"\s*\(Action Verb:[^)]*\)", "", text)
    # Remove markdown bold/italic
    text = text.replace("**", "").replace("__", "")
    return text.strip()


def _check_resume_issues(text: str) -> list:
    """Check for content integrity issues (fabrication signals, filler phrases)."""
    issues = []

    FILLERS = [
        "responsible for", "helped with", "worked on",
        "demonstrating expertise", "showcasing ability",
        "assisted in", "participated in", "involved in",
    ]
    found = [f for f in FILLERS if f in text.lower()]
    if found:
        issues.append(f"Filler phrases — remove: {found}")

    return issues

# ── STEP 2: CLAUDE PIPELINE ───────────────────────────────────────────────


# def process_with_claude(scraped_jobs):
# limit = 3  # for testing
def process_with_claude(scraped_jobs, limit=None):
    ai_mode = os.environ.get("AI_MODE", "groq")

    # Fit scoring is now rule-based (zero LLM calls, instant, deterministic).
    from pipeline.rule_scorer import score_fit_rules
    from pipeline.ollama_tasks import score_tailored_resume as _score_tailored_ollama
    from pipeline.claude_tasks import score_tailored_resume as _score_tailored_groq
    score_tailored_resume = (
        _score_tailored_ollama if ai_mode == "ollama" else _score_tailored_groq
    )

    if ai_mode == "ollama":
        from pipeline.ollama_tasks import (
            tailor_resume, generate_cover_letter, generate_outreach_email
        )
    else:
        from pipeline.claude_tasks import (
            tailor_resume, generate_cover_letter, generate_outreach_email
        )
    from db import get_conn

    # Get jobs with no fit score yet
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM applications
        WHERE fit_score IS NULL
           OR tailored_resume IS NULL
    """).fetchall()
    pending = [dict(r) for r in rows]

    if not pending:
        console.print("[yellow]No new jobs to process.[/yellow]")
        return

    #   console.print(f"\n[cyan]Processing {len(pending)} jobs through Claude...[/cyan]\n")
    # Optional limit for testing
    if limit:
        pending = pending[:limit]
    console.print(f"\n[cyan]Processing {len(pending)} jobs through Claude...[/cyan]\n")

    # Optional limit for testing
    limit = int(os.environ.get("PROCESS_LIMIT", 0))
    if limit:
        pending = pending[:limit]
        console.print(f"[yellow]Limiting to {limit} jobs this run.[/yellow]\n")

    # Funnel drop counters
    _drops = {"blacklist": 0, "title": 0, "overlevel": 0,
              "location": 0, "keyword": 0, "fit": 0}

    for job in track(pending, description="Claude working..."):
        try:
            company  = job.get("company", "")
            title    = job.get("title", "")
            jd       = job.get("description", "")
            location = job.get("location", "")

            # ── Stage 0: hard filters (free) ──────────────────────────────
            if is_blacklisted(company):
                console.print(f"  [dim]↷ Blacklisted: {company}[/dim]")
                mark_applied(job["job_id"], status=2, notes="Blacklisted company")
                _drops["blacklist"] += 1
                continue
            if is_off_target_title(title):
                console.print(f"  [dim]↷ Off-target title: {title}[/dim]")
                mark_applied(job["job_id"], status=2, notes="Off-target title")
                _drops["title"] += 1
                continue
            if is_overleveled(jd):
                console.print(f"  [dim]↷ Overleveled: {title} @ {company}[/dim]")
                mark_applied(job["job_id"], status=2, notes="Overleveled — 6+ years required")
                _drops["overlevel"] += 1
                continue

            # ── Stage 1: location check (free) ──────────────────────────────
            if is_wrong_location(location, jd):
                console.print(f"  [dim]↷ Wrong location: {location or '?'}[/dim]")
                mark_applied(job["job_id"], status=2, notes=f"Wrong location: {location}")
                _drops["location"] += 1
                continue

            # ── Stage 2: keyword pre-score (free — string match only) ───────────
            kp = keyword_prescore(jd, title)
            if kp < KEYWORD_PRESCORE_MIN:
                console.print(
                    f"  [dim]↷ Low keyword match ({kp:.0%}): {title}[/dim]"
                )
                mark_applied(job["job_id"], status=2,
                             notes=f"Keyword pre-score {kp:.0%} < {KEYWORD_PRESCORE_MIN:.0%}")
                _drops["keyword"] += 1
                continue

            # ── Stage 3: rule-based fit score (zero LLM, instant) ──────────
            fit = score_fit_rules(job, BASE_RESUME)
            score = fit.get("score", 0)
            color = "green" if score >= FIT_SCORE_THRESHOLD else "red"
            console.print(
                f"  [bold]{job['title']}[/bold] @ {job['company']} — "
                f"Fit: [{color}]{score}/100[/{color}]  "
                f"[dim](kw={fit['keyword_overlap']} ti={fit['title_match']} "
                f"exp={fit['experience_level']} tech={fit['tech_stack']})[/dim]"
            )

            if score < FIT_SCORE_THRESHOLD:
                mark_applied(
                    job["job_id"], status=2, notes=f"Fit score {score} below threshold"
                )
                update_claude_outputs(job["job_id"], fit, "", {}, "", {})
                _drops["fit"] += 1
                continue

            # 2. Tailor resume — 3-tier lookup: approved → cached → generate
            from pipeline.cluster_cache import (
                map_to_cluster, get_approved_resume, get_cached_resume,
                save_to_cache, copy_cluster_pdf, save_cluster_pdf,
            )
            cluster = map_to_cluster(job.get("title", ""))

            # ── Tier 1: hand-approved resume ──────────────────────────────
            approved_text = (
                get_approved_resume(cluster)
                if cluster and RESUME_MODE != "generate"
                else None
            )
            if approved_text:
                tailored  = approved_text
                cache_hit = True
                quality   = {
                    "overall": 95, "factual_accuracy": 100,
                    "ats_score": 90, "clarity": 95,
                    "drift_warning": False, "notes": "hand-approved resume",
                }
                console.print(
                    f"    [green]✓ Approved resume used "
                    f"({ROLE_CLUSTERS[cluster]['label']})[/green]"
                )

            # ── Tier 2: AI-generated cluster cache ────────────────────────
            elif RESUME_MODE == "approved_only":
                console.print(
                    f"    [yellow]↷ No approved resume for cluster "
                    f"'{cluster or 'none'}' — skipping (approved_only mode)[/yellow]"
                )
                mark_applied(job["job_id"], status=2, notes="No approved resume for cluster")
                continue
            else:
                cached_text = get_cached_resume(cluster) if cluster else None
                cache_hit   = cached_text is not None
                if cache_hit:
                    tailored = cached_text
                    quality  = {
                        "overall": 90, "factual_accuracy": 95,
                        "ats_score": 85, "clarity": 90,
                        "drift_warning": False, "notes": "cluster cache hit",
                    }
                    console.print(
                        f"    [dim]↩ Cached resume reused "
                        f"({ROLE_CLUSTERS[cluster]['label']})[/dim]"
                    )

            # ── Tier 3: generate fresh ─────────────────────────────────────
            if not approved_text and not (cluster and cache_hit):
                MAX_ATTEMPTS = 3
                missing_kw = fit.get("missing_keywords", [])
                tailored = tailor_resume(job, missing_keywords=missing_kw)
                tailored = _clean_model_output(tailored)

                for attempt in range(MAX_ATTEMPTS):
                    issues = _check_resume_issues(tailored)
                    if not issues:
                        break
                    console.print(f"    [yellow]⚠ Check failed (attempt {attempt+1}) — fixing: {', '.join(issues)}[/yellow]")
                    fix_prompt = f"""The resume below has these ATS issues that MUST be fixed:
            {chr(10).join(f'- {i}' for i in issues)}

            Fix ONLY these issues. Keep everything else exactly the same.
            Output ONLY the corrected resume text. No labels, no commentary.

            RESUME TO FIX:
            {tailored}"""
                    if os.environ.get("AI_MODE") == "ollama":
                        from pipeline.ollama_tasks import _call
                    else:
                        from pipeline.claude_tasks import _call
                    tailored = _clean_model_output(_call(fix_prompt))

                # 3. Score tailored resume
                quality = score_tailored_resume(tailored)
                if quality.get("drift_warning"):
                    console.print(
                        f"    [yellow]⚠ Drift warning — factual accuracy: {quality.get('factual_accuracy')}/100[/yellow]"
                    )

                if quality.get("overall", 100) < RESUME_SIMILARITY_MIN:
                    console.print(
                        f"    [red]Resume quality too low ({quality.get('overall')}), skipping.[/red]"
                    )
                    mark_applied(job["job_id"], status=2, notes="Resume quality too low")
                    update_claude_outputs(job["job_id"], fit, tailored, quality, "", {})
                    continue

                # Save to cluster cache so subsequent jobs in same cluster are instant
                if cluster:
                    save_to_cache(cluster, tailored, job)

            # 4. Cover letter
            cover = generate_cover_letter(job)

            # 5. Outreach email
            outreach = generate_outreach_email(job)

            # Save to DB
            update_claude_outputs(
                job["job_id"], fit, tailored, quality, cover, outreach
            )

            # Save to disk
            job_dir = os.path.join(OUTPUT_DIR, job["job_id"])
            os.makedirs(job_dir, exist_ok=True)

            with open(f"{job_dir}/resume_tailored.txt", "w") as f:
                f.write(tailored)
            with open(f"{job_dir}/cover_letter.txt", "w") as f:
                f.write(cover)
            with open(f"{job_dir}/outreach_email.txt", "w") as f:
                f.write(
                    f"Subject: {outreach.get('subject', '')}\n\n{outreach.get('body', '')}"
                )
            with open(f"{job_dir}/fit_report.json", "w") as f:
                json.dump({"fit": fit, "resume_quality": quality}, f, indent=2)

            console.print(
                f"    [green]✓ Materials saved → output/applications/{job['job_id']}/[/green]"
            )
            # PDF — copy from cluster cache (instant) or compile fresh
            try:
                job_dir  = os.path.join(OUTPUT_DIR, job["job_id"])
                title_s  = (job.get("title",   "Role")   .replace(" ", "-")
                    .replace(",", "").replace("/", "-")[:40])
                company_s = (job.get("company", "Company").replace(" ", "-")
                    .replace(",", "").replace("/", "-")[:25])
                pdf_name     = f"{title_s}-Navaneeta-Padmakumar-{company_s}.pdf"
                pdf_standard = os.path.join(job_dir, "resume_tailored.pdf")
                pdf_path     = os.path.join(job_dir, pdf_name)

                from generate_html_pdf import generate_pdf as _gen_pdf
                if cache_hit and copy_cluster_pdf(cluster, job_dir, pdf_name):
                    console.print(f"    [green]✓ Copied cluster PDF → {pdf_name}[/green]")
                else:
                    resume_text = tailored or BASE_RESUME
                    _gen_pdf(resume_text, pdf_path)
                    if os.path.exists(pdf_path):
                        shutil.copy(pdf_path, pdf_standard)
                        console.print(f"    [green]✓ PDF generated → {pdf_name}[/green]")
                        if cluster:
                            save_cluster_pdf(cluster, pdf_path)
                    else:
                        console.print("    [yellow]⚠ PDF generation failed — resume text saved[/yellow]")
            except Exception as e:
                console.print(f"    [yellow]⚠ PDF generation skipped: {e}[/yellow]")

        except Exception as e:
            console.print(f"    [red]Error: {e}[/red]")
            mark_applied(job["job_id"], status=3, notes=str(e))

    # ── Funnel summary ────────────────────────────────────────────────────
    total_dropped = sum(_drops.values())
    llm_seen = len(pending) - total_dropped + _drops["fit"]
    tbl = Table(title="Processing funnel", show_header=True, header_style="bold cyan")
    tbl.add_column("Stage",   style="dim")
    tbl.add_column("Dropped", justify="right")
    tbl.add_column("Reason")
    tbl.add_row("0a Blacklist",      str(_drops["blacklist"]), "company on blacklist")
    tbl.add_row("0b Off-target",     str(_drops["title"]),     "title clearly unrelated")
    tbl.add_row("0c Overleveled",    str(_drops["overlevel"]), "6+ years required")
    tbl.add_row("1  Location",       str(_drops["location"]),  "not India / not remote")
    tbl.add_row("2  Keyword match",  str(_drops["keyword"]),   f"< {KEYWORD_PRESCORE_MIN:.0%} skill overlap")
    tbl.add_row("3  LLM fit score",  str(_drops["fit"]),       f"score < {FIT_SCORE_THRESHOLD}")
    tbl.add_row("[bold]LLM calls made[/bold]",
                f"[bold]{llm_seen}[/bold]",
                f"of {len(pending)} total ({len(pending) - total_dropped} passed all gates)")
    console.print(tbl)


# ── STEP 3: AUTO-APPLY ────────────────────────────────────────────────────


def auto_apply(dry_run: bool = False):
    """
    For every job that has generated materials (PDF + cover letter) and
    hasn't been applied to yet:
      - easy apply jobs  → LinkedIn / Indeed bot
      - full_form jobs   → Greenhouse / Lever / Ashby bot
                           (unknown ATS → marked manual_required)
    """
    import time
    from applicator.base import find_pdf
    from applicator.ats import detect_ats, route as ats_route
    from config import HEADLESS

    easy_jobs = get_easy_apply_pending()
    full_jobs = get_full_form_pending()

    # Run the same cheap pre-filters as process_with_claude so nothing
    # that slipped in before filters were added reaches Playwright.
    def _passes_filters(job: dict) -> bool:
        co = job.get("company", "")
        ti = job.get("title", "")
        jd = job.get("description", "") or ""
        lo = job.get("location", "") or ""
        if is_blacklisted(co):
            return False
        if is_off_target_title(ti):
            return False
        if is_overleveled(jd):
            return False
        if is_wrong_location(lo, jd):
            return False
        if keyword_prescore(jd, ti) < KEYWORD_PRESCORE_MIN:
            return False
        return True

    def _gate(jobs: list) -> list:
        kept, dropped = [], 0
        for j in jobs:
            if _passes_filters(j):
                kept.append(j)
            else:
                console.print(f"  [dim]↷ Filtered at apply gate: {j.get('title','')} @ {j.get('company','')}[/dim]")
                mark_applied(j["job_id"], status=2, notes="Filtered at apply gate")
                dropped += 1
        if dropped:
            console.print(f"  [dim]({dropped} jobs filtered before Playwright starts)[/dim]")
        return kept

    easy_jobs = _gate(easy_jobs)
    full_jobs  = _gate(full_jobs)
    total     = len(easy_jobs) + len(full_jobs)

    if not total:
        console.print("[yellow]No jobs ready to auto-apply (all filtered or none pending).[/yellow]")
        return

    tag = "[dim][DRY RUN][/dim] " if dry_run else ""
    console.print(
        f"\n[cyan]{tag}Auto-apply: {len(easy_jobs)} easy-apply "
        f"+ {len(full_jobs)} full-form[/cyan]\n"
    )

    # Lazy-init platform applicators (only import Playwright when needed)
    _platform_cache: dict = {}

    def _get_platform_applicator(platform: str):
        if platform not in _platform_cache:
            if platform == "linkedin":
                from applicator.linkedin import LinkedInApplicator
                _platform_cache[platform] = LinkedInApplicator(headless=HEADLESS)
            elif platform == "indeed":
                from applicator.indeed import IndeedApplicator
                _platform_cache[platform] = IndeedApplicator(headless=HEADLESS)
        return _platform_cache.get(platform)

    all_jobs = [("easy", j) for j in easy_jobs] + [("full_form", j) for j in full_jobs]

    applied = skipped = failed = 0

    for apply_type, job in all_jobs:
        jid  = job["job_id"]
        name = f"[bold]{job['title']}[/bold] @ {job['company']}"

        pdf = find_pdf(jid)
        if not pdf:
            console.print(f"  [red]✗ No PDF found for {name} — skipping[/red]")
            skipped += 1
            continue

        console.print(f"  Applying: {name} ({apply_type})")
        logging.info(f"auto_apply: {jid} — {apply_type}")

        try:
            if apply_type == "easy":
                applicator = _get_platform_applicator(job["platform"])
                if not applicator:
                    console.print(f"    [yellow]No bot for platform '{job['platform']}' — skipping[/yellow]")
                    skipped += 1
                    continue
            else:  # full_form
                url = job.get("apply_url_direct") or job.get("apply_url") or ""
                ats = detect_ats(url)
                applicator = ats_route(url, headless=HEADLESS)
                if not applicator:
                    console.print(
                        f"    [yellow]Unknown ATS ({ats or 'undetected'}) — queued for manual apply[/yellow]\n"
                        f"    URL: {url}"
                    )
                    mark_applied(jid, status=2, notes=f"Manual required — ATS: {ats or 'unknown'}")
                    skipped += 1
                    continue

            result = applicator.apply(job, pdf, dry_run=dry_run)

            if result["success"]:
                if not dry_run:
                    mark_applied(jid, status=1, notes=result.get("notes", ""))
                console.print(f"    [green]✓ {result.get('notes', 'Applied')}[/green]")
                applied += 1
            else:
                if not dry_run:
                    mark_applied(jid, status=3, notes=result.get("notes", ""))
                console.print(f"    [red]✗ {result.get('notes', 'Failed')}[/red]")
                failed += 1

        except Exception as e:
            console.print(f"    [red]Error: {e}[/red]")
            logging.error(f"auto_apply error for {jid}: {e}")
            if not dry_run:
                mark_applied(jid, status=3, notes=str(e))
            failed += 1

        time.sleep(3)  # Rate-limit between applications

    console.print(
        f"\n[green]Applied: {applied}[/green]  "
        f"[yellow]Skipped/manual: {skipped}[/yellow]  "
        f"[red]Failed: {failed}[/red]"
    )
    logging.info(f"auto_apply finished — applied:{applied} skipped:{skipped} failed:{failed}")


# ── STATUS TABLE ──────────────────────────────────────────────────────────


def print_status(include_actions: bool = False):
    rows = get_all()
    if not rows:
        console.print("[yellow]No applications yet. Run: python main.py --discover[/yellow]")
        return

    type_color = {"easy": "green", "full_form": "yellow", "unknown": "dim"}

    def _tier(score):
        if score is None:
            return ("Unscored",       "dim")
        if score >= 80:
            return ("Strong (80+)",   "green")
        if score >= 70:
            return ("Good   (70-79)", "cyan")
        if score >= 55:
            return ("Moderate (55-69)", "yellow")
        return ("Weak   (<55)", "red")

    # Group pending jobs by tier; applied/skipped shown in a compact summary.
    pending = [r for r in rows if r.get("applied") == 0]
    applied = [r for r in rows if r.get("applied") == 1]
    skipped = [r for r in rows if r.get("applied") == 2]

    # Sort pending by score desc, then date desc
    pending.sort(key=lambda r: (-(r.get("fit_score") or 0), r.get("date_posted") or ""), reverse=False)

    tiers_order = ["Strong (80+)", "Good   (70-79)", "Moderate (55-69)", "Weak   (<55)", "Unscored"]
    tier_colors = {
        "Strong (80+)":    "green",
        "Good   (70-79)": "cyan",
        "Moderate (55-69)": "yellow",
        "Weak   (<55)":   "red",
        "Unscored":        "dim",
    }
    tier_jobs: dict[str, list] = {t: [] for t in tiers_order}
    for r in pending:
        label, _ = _tier(r.get("fit_score"))
        tier_jobs[label].append(r)

    for tier_label in tiers_order:
        jobs_in_tier = tier_jobs[tier_label]
        if not jobs_in_tier:
            continue
        color = tier_colors[tier_label]
        tbl = Table(
            title=f"[{color}]{tier_label}[/{color}]  ({len(jobs_in_tier)} jobs)",
            show_lines=False,
            header_style="bold",
            show_header=True,
        )
        tbl.add_column("Fit",      justify="right", style=color, width=5)
        tbl.add_column("Posted",   justify="right", width=6)
        tbl.add_column("Platform", style="cyan",    width=9)
        tbl.add_column("Title",                    width=34)
        tbl.add_column("Company",                  width=22)
        tbl.add_column("Type",     justify="center",width=10)
        for r in jobs_in_tier:
            atype     = r.get("apply_type") or "?"
            atype_str = f"[{type_color.get(atype, 'white')}]{atype}[/]"
            posted    = (r.get("date_posted") or "—")[-5:]
            score_str = str(r.get("fit_score")) if r.get("fit_score") else "—"
            tbl.add_row(
                score_str,
                posted,
                (r.get("platform") or "").capitalize(),
                (r.get("title")    or "")[:34],
                (r.get("company")  or "")[:22],
                atype_str,
            )
        console.print(tbl)

    console.print(
        f"\n[green]✓ Applied: {len(applied)}[/green]  "
        f"[cyan]⏳ Shortlisted: {len(pending)}[/cyan]  "
        f"[dim]⊘ Skipped: {len(skipped)}[/dim]"
    )

    if include_actions:
        from pipeline.rule_scorer import _gap_mitigations
        import json
        actionable = [r for r in pending if (r.get("fit_score") or 0) >= 70]
        if actionable:
            console.print("\n[bold yellow]Action Items — Strong & Good matches[/bold yellow]")
            for r in actionable[:8]:
                gaps_raw = r.get("fit_gaps") or "[]"
                try:
                    gaps = json.loads(gaps_raw) if isinstance(gaps_raw, str) else gaps_raw
                except Exception:
                    gaps = []
                jd = (r.get("description") or "").lower()
                resume_lc = BASE_RESUME.lower()
                hints = _gap_mitigations(gaps, jd, resume_lc)
                score = r.get("fit_score", "?")
                title = (r.get("title") or "")[:35]
                co    = (r.get("company") or "")[:20]
                console.print(f"  [{score}] [cyan]{title}[/cyan] @ {co}")
                if hints:
                    for h in hints:
                        console.print(f"       [dim]→ {h}[/dim]")
                else:
                    console.print("       [dim]→ No specific gaps — good to apply[/dim]")


def run_prep(top_n: int = 5):
    """
    Segment 1 — rank top N qualified roles and write a role-highlighted
    resume variation for each.  Zero LLM calls: the variation is the
    original resume text with a role-specific summary prepended.
    Edit resumes/<cluster>.txt manually to fine-tune each version.
    """
    from pipeline.role_detector import detect_top_roles

    console.print(f"\n[bold cyan]Segment 1 — Resume Prep[/bold cyan]  (top {top_n} roles)\n")

    roles = detect_top_roles(BASE_RESUME, n=top_n)

    # ── Role ranking table ──────────────────────────────────────────────────
    tbl = Table(title="Roles your resume qualifies for", header_style="bold cyan",
                show_lines=False)
    tbl.add_column("#",      justify="right", width=3)
    tbl.add_column("Score",  justify="right", width=6)
    tbl.add_column("Cluster",               width=20)
    tbl.add_column("Role",                  width=26)
    tbl.add_column("Gaps (things to add manually)")
    rank_colors = ["green", "green", "cyan", "cyan", "yellow"]
    for i, role in enumerate(roles):
        color = rank_colors[min(i, len(rank_colors) - 1)]
        gaps = "; ".join(role["gaps"][:2]) if role["gaps"] else "—"
        tbl.add_row(
            str(i + 1),
            f"[{color}]{role['score']}[/{color}]",
            role["cluster"],
            role["label"],
            f"[dim]{gaps}[/dim]",
        )
    console.print(tbl)

    # ── Write role variations (no LLM) ─────────────────────────────────────
    os.makedirs("resumes", exist_ok=True)
    console.print(f"\n[cyan]Writing {top_n} resume variations…[/cyan]\n")

    for i, role in enumerate(roles, 1):
        cluster  = role["cluster"]
        out_path = f"resumes/{cluster}.txt"
        if os.path.exists(out_path):
            console.print(
                f"  [{i}/{top_n}] [dim]Skipping {cluster} "
                f"— already exists at {out_path}[/dim]"
            )
            continue

        with open(out_path, "w") as f:
            f.write(BASE_RESUME)
        console.print(f"  [{i}/{top_n}] [green]✓ Saved → {out_path}[/green]")
        if role["missing"]:
            console.print(
                f"         [dim]Keywords to consider adding: "
                f"{', '.join(role['missing'][:6])}[/dim]"
            )

    console.print(
        "\n[dim]Each file is an exact copy of your original resume.\n"
        "Open resumes/<cluster>.txt and tweak skills ordering or wording for that role.\n"
        "The pipeline will use these automatically when applying.[/dim]"
    )


def run_discover(limit=None):
    """Segment 2 — scrape fresh jobs, score all, display tiered shortlist."""
    from pipeline.rule_scorer import score_fit_rules
    from db import get_conn, update_claude_outputs
    import config as _cfg
    from pipeline.experiment_tracker import (
        build_params, start_run, log_metrics,
        log_filter_breakdown, log_top_jobs, end_run,
    )

    console.print("\n[bold cyan]Segment 2 — Discover & Score[/bold cyan]\n")

    # Start MLflow run
    start_run(build_params(_cfg))

    # Step 1: scrape
    scrape_all()

    # Step 2: classify
    classify_jobs()

    # Step 3: score all unscored jobs instantly (zero LLM)
    conn = get_conn()
    unscored = [
        dict(r) for r in conn.execute(
            "SELECT * FROM applications WHERE fit_score IS NULL AND applied = 0"
        ).fetchall()
    ]
    conn.close()

    if limit:
        unscored = unscored[:limit]

    dropped = scored = 0
    filter_drops: dict[str, int] = {}
    scores_seen: list[int] = []
    for job in unscored:
        co = job.get("company", "")
        ti = job.get("title",   "")
        jd = job.get("description", "") or ""
        lo = job.get("location", "") or ""

        # Cheap pre-filters first
        reason = None
        if is_blacklisted(co):
            reason = "Blacklisted company"
        elif is_off_target_title(ti):
            reason = "Off-target title"
        elif is_ghost_job(jd):
            reason = "Ghost job — posting closed"
        elif is_stale_posting(job.get("date_posted")):
            reason = "Stale posting (>21 days)"
        elif is_overleveled(jd):
            reason = "Overleveled"
        elif is_wrong_location(lo, jd):
            reason = "Wrong location"
        elif keyword_prescore(jd, ti) < KEYWORD_PRESCORE_MIN:
            reason = "Low keyword match"

        if reason:
            mark_applied(job["job_id"], status=2, notes=reason)
            filter_drops[reason] = filter_drops.get(reason, 0) + 1
            dropped += 1
            continue

        fit = score_fit_rules(job, BASE_RESUME)
        update_claude_outputs(job["job_id"], fit, "", {}, "", {})
        scores_seen.append(fit["score"])
        scored += 1

    console.print(
        f"\n[green]Scored {scored} jobs[/green]  "
        f"[dim]({dropped} filtered out before scoring)[/dim]\n"
    )

    # Step 4: deep eval for top jobs (Groq, capped at DEEP_EVAL_LIMIT)
    if os.environ.get("GROQ_API_KEY") or GROQ_API_KEY:
        from pipeline.deep_eval import deep_eval_jobs, DEEP_EVAL_MIN, format_deep_eval
        import json as _json
        conn2 = get_conn()
        top_jobs = [
            dict(r) for r in conn2.execute(
                "SELECT * FROM applications WHERE fit_score >= ? AND applied = 0"
                " ORDER BY fit_score DESC",
                (DEEP_EVAL_MIN,)
            ).fetchall()
        ]
        conn2.close()
        if top_jobs:
            console.print(f"[cyan]Deep-evaluating top {len(top_jobs[:10])} jobs via Groq...[/cyan]")
            evaluated = deep_eval_jobs(top_jobs, BASE_RESUME)
            for ej in evaluated:
                de = ej.get("deep_eval") or {}
                if de:
                    existing_fit = {
                        "score":     ej.get("fit_score"),
                        "verdict":   ej.get("fit_verdict", ""),
                        "strengths": _json.loads(ej.get("fit_strengths") or "[]"),
                        "gaps":      _json.loads(ej.get("fit_gaps") or "[]"),
                    }
                    existing_fit["deep_eval_summary"] = format_deep_eval(de)
                    update_claude_outputs(
                        ej["job_id"], existing_fit,
                        ej.get("tailored_resume", ""),
                        {}, "", {}
                    )

    # Step 5: log MLflow metrics and close run
    conn3 = get_conn()
    all_scored = [dict(r) for r in conn3.execute(
        "SELECT * FROM applications WHERE fit_score IS NOT NULL AND applied = 0"
    ).fetchall()]
    conn3.close()

    strong  = sum(1 for j in all_scored if (j.get("fit_score") or 0) >= 80)
    good    = sum(1 for j in all_scored if 70 <= (j.get("fit_score") or 0) < 80)
    avg_score = (sum(scores_seen) / len(scores_seen)) if scores_seen else 0

    log_metrics({
        "jobs_scraped":   len(unscored) + dropped,
        "jobs_filtered":  dropped,
        "jobs_scored":    scored,
        "avg_fit_score":  round(avg_score, 1),
        "strong_matches": strong,
        "good_matches":   good,
    })
    log_filter_breakdown(filter_drops)
    log_top_jobs(all_scored)
    end_run()

    # Step 6: tiered display
    print_status(include_actions=True)


# ── MAIN ──────────────────────────────────────────────────────────────────


def main():
    init_db()
    migrate_db()
    _acquire_lock()
    _setup_logging()

    # ── AI mode from env var or config (cron-safe — no interactive prompt) ─
    ai_mode = os.environ.get("AI_MODE") or AI_MODE
    if ai_mode == "groq" and not os.getenv("GROQ_API_KEY"):
        console.print("[red]AI_MODE=groq but GROQ_API_KEY is not set.[/red]")
        console.print("[yellow]Either export GROQ_API_KEY='...' or set AI_MODE=ollama in config.py[/yellow]")
        sys.exit(1)
    os.environ["AI_MODE"] = ai_mode
    console.print(f"\n[bold cyan]Apply Easy — Job Automator[/bold cyan]  (mode: [green]{ai_mode}[/green])\n")

    parser = argparse.ArgumentParser(
        description="Apply Easy — Job Automator powered by Claude"
    )
    parser.add_argument("--prep",      action="store_true", help="Segment 1: detect top roles + generate resume variations")
    parser.add_argument("--discover",  action="store_true", help="Segment 2: scrape + score all jobs + show tiered shortlist")
    parser.add_argument("--scrape",    action="store_true", help="Scrape new jobs only")
    parser.add_argument("--classify",  action="store_true", help="Classify jobs as easy-apply or full-form")
    parser.add_argument("--process",   action="store_true", help="AI tailor resume + cover letter for shortlisted jobs")
    parser.add_argument("--apply",     action="store_true", help="Auto-apply to pending jobs using generated resumes")
    parser.add_argument("--dry-run",   action="store_true", help="Simulate --apply without submitting (safe for testing)")
    parser.add_argument("--status",         action="store_true", help="Show tiered shortlist table")
    parser.add_argument("--resume-status",   action="store_true", help="Show resume tier status for all clusters")
    parser.add_argument("--clean",           action="store_true", help="Retroactively skip all pending jobs that fail pre-filters (no LLM)")
    parser.add_argument("--promote",          metavar="CLUSTER",   help="Promote cached resume to approved for a cluster (e.g. ml_ai)")
    parser.add_argument("--top",              type=int, default=5,  help="Number of top roles for --prep (default: 5)")
    parser.add_argument("--limit",            type=int, default=None, help="Max jobs to process per run")
    args = parser.parse_args()

    if args.prep:
        run_prep(top_n=args.top)
        return

    if args.discover:
        run_discover(limit=args.limit)
        return

    if args.status:
        print_status()
        return

    if getattr(args, "resume_status", False):
        from pipeline.cluster_cache import list_all_resumes
        rows = list_all_resumes()
        tbl  = Table(title=f"Resume tiers  (mode: {RESUME_MODE})",
                     show_header=True, header_style="bold cyan")
        tbl.add_column("Cluster")
        tbl.add_column("Label")
        tbl.add_column("Source",   justify="center")
        tbl.add_column("Age",      justify="right")
        tbl.add_column("PDF",      justify="center")
        src_color = {"approved": "green", "cached": "yellow", "none": "red"}
        for r in rows:
            color = src_color.get(r["source"], "white")
            stale = " [dim](stale)[/dim]" if r["stale"] else ""
            age   = f"{r['age_days']}d{stale}" if r["age_days"] is not None else "—"
            pdf   = "[green]✓[/green]" if r["has_pdf"] else "[dim]—[/dim]"
            tbl.add_row(
                r["cluster"],
                r["label"],
                f"[{color}]{r['source']}[/{color}]",
                age,
                pdf,
            )
        console.print(tbl)
        console.print(
            "\n[dim]To promote a cached resume: python main.py --promote <cluster>[/dim]\n"
            "[dim]To use hand-crafted: drop resumes/<cluster>.txt into the resumes/ folder[/dim]"
        )
        return

    if getattr(args, "clean", False):
        # Retroactively run pre-filters on all pending jobs and mark
        # off-target / garbage ones as skipped without any LLM calls.
        import sqlite3 as _sq
        conn = _sq.connect("output/applications.db")
        conn.row_factory = _sq.Row
        jobs = [dict(r) for r in conn.execute(
            "SELECT * FROM applications WHERE applied=0"
        )]
        skipped_n = 0
        for j in jobs:
            co = j.get("company", "")
            ti = j.get("title", "")
            jd = j.get("description", "") or ""
            lo = j.get("location", "") or ""
            reason = None
            if is_blacklisted(co):
                reason = "Blacklisted company"
            elif is_off_target_title(ti):
                reason = "Off-target title"
            elif is_overleveled(jd):
                reason = "Overleveled"
            elif is_wrong_location(lo, jd):
                reason = "Wrong location"
            elif keyword_prescore(jd, ti) < KEYWORD_PRESCORE_MIN:
                reason = "Low keyword match"
            if reason:
                conn.execute(
                    "UPDATE applications SET applied=2, notes=? WHERE job_id=?",
                    (reason, j["job_id"]),
                )
                console.print(f"  [dim]↷ {reason}: {ti[:40]} @ {co[:25]}[/dim]")
                skipped_n += 1
        conn.commit()
        conn.close()
        console.print(f"\n[green]✓ Cleaned {skipped_n} jobs out of {len(jobs)} pending.[/green]")
        console.print("[dim]Run --status to see what remains.[/dim]")
        return

    if getattr(args, "promote", None):
        from pipeline.cluster_cache import promote_to_approved
        cluster = args.promote
        try:
            path = promote_to_approved(cluster)
            console.print(f"[green]✓ Promoted '{cluster}' cache → {path}[/green]")
            console.print("[dim]Edit that file, then re-run --process to use it.[/dim]")
        except FileNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
        return
    if args.scrape:
        scrape_all()
        return
    if args.classify:
        classify_jobs()
        return
    if args.process:
        process_with_claude([], limit=args.limit)
        return
    if getattr(args, "apply", False) or getattr(args, "dry_run", False):
        auto_apply(dry_run=getattr(args, "dry_run", False))
        return

    # Default: full pipeline
    console.print("\n[bold cyan]Apply Easy — Full Pipeline[/bold cyan]\n")
    scraped = scrape_all()
    classify_jobs()
    process_with_claude(scraped, limit=args.limit)
    auto_apply()
    print_status()


if __name__ == "__main__":
    main()
