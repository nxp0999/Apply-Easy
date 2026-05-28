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
    FIT_SCORE_THRESHOLD,
    RESUME_SIMILARITY_MIN,
    OUTPUT_DIR,
    ROLE_CLUSTERS,
)
from resume_rules import STRONG_VERBS
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

    all_jobs = _scrape()

    for job in all_jobs:
        insert_job(job)

    console.print(f"\n[green]✓ Scraped {len(all_jobs)} unique jobs.[/green]")
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
    # Strip markdown formatting that confuses the bullet checker
    text = text.replace("**", "").replace("__", "")
    """Run ATS checks and return list of issues found."""
    import re
    issues = []

    # Extract bullets
    bullets = [ln.strip().lstrip("-•* ").strip()
               for ln in text.splitlines()
               if ln.strip().startswith(("-", "•", "*"))]

    # 1. Bullet count
    if len(bullets) > 20:
        issues.append(f"Too many bullets: {len(bullets)} — reduce to max 20")

    # 2. Quantified bullets
    quantified = [b for b in bullets if re.search(r"\d+", b)]
    pct = len(quantified) / len(bullets) * 100 if bullets else 0
    if pct < 80:
        unquantified = [b[:60] for b in bullets if not re.search(r"\d+", b)]
        issues.append(f"Only {pct:.0f}% bullets quantified — add numbers to: {unquantified[:3]}")

    # 3. Repeated verbs
    verb_counts = {}
    for b in bullets:
        first = b.split()[0].lower().rstrip(".,") if b else ""
        if first in STRONG_VERBS:
            verb_counts[first] = verb_counts.get(first, 0) + 1
    overused = {v: c for v, c in verb_counts.items() if c > 1}
    if overused:
        issues.append(f"Overused action verbs (max 2 each): {overused} — replace with different verbs")

    # 4. Date consistency
    short = re.findall(r"\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", text)
    long_ = re.findall(r"\b(January|February|March|April|June|July|August|September|October|November|December)\b", text)
    if short and long_:
        issues.append(f"Inconsistent dates — change all short months {set(short)} to long format (e.g. January not Jan)")

    # 5. Filler phrases
    FILLERS = ["responsible for","helped with","worked on","demonstrating expertise",
               "showcasing ability","assisted in","participated in","involved in"]
    found = [f for f in FILLERS if f in text.lower()]
    if found:
        issues.append(f"Filler phrases found — remove: {found}")

    # 6. Similar bullets
    seen = []
    for b in bullets:
        words = set(b.lower().split())
        for s in seen:
            overlap = len(words & set(s.lower().split())) / max(len(words), 1)
            if overlap > 0.75:
                issues.append(f"Duplicate bullet — rewrite to be unique: '{b[:50]}'")
                break
        seen.append(b)

    return issues

# ── STEP 2: CLAUDE PIPELINE ───────────────────────────────────────────────


# def process_with_claude(scraped_jobs):
# limit = 3  # for testing
def process_with_claude(scraped_jobs, limit=None):
    ai_mode = os.environ.get("AI_MODE", "groq")

    # Use Groq for scoring when a key is available (faster, more accurate).
    # Fall back to the local model if running in pure-offline / Ollama mode.
    if os.getenv("GROQ_API_KEY"):
        from pipeline.claude_tasks import score_fit, score_tailored_resume
    else:
        from pipeline.ollama_tasks import score_fit, score_tailored_resume

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

    for job in track(pending, description="Claude working..."):
        try:
            # 1. Fit score
            fit = score_fit(job)
            score = fit.get("score", 0)
            color = "green" if score >= FIT_SCORE_THRESHOLD else "red"
            console.print(
                f"  [bold]{job['title']}[/bold] @ {job['company']} — "
                f"Fit: [{color}]{score}/100[/{color}]"
            )

            if score < FIT_SCORE_THRESHOLD:
                mark_applied(
                    job["job_id"], status=2, notes=f"Fit score {score} below threshold"
                )
                update_claude_outputs(job["job_id"], fit, "", {}, "", {})
                continue

            # 2. Tailor resume — check cluster cache first
            from pipeline.cluster_cache import (
                map_to_cluster, get_cached_resume, save_to_cache,
                copy_cluster_pdf, save_cluster_pdf,
            )
            cluster     = map_to_cluster(job.get("title", ""))
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
            else:
                MAX_ATTEMPTS = 3
                tailored = tailor_resume(job)
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
                from generate_tex import process_job as gen_tex
                import subprocess
                job_dir  = os.path.join(OUTPUT_DIR, job["job_id"])
                title_s  = (job.get("title",   "Role")   .replace(" ", "-")
                    .replace(",", "").replace("/", "-")[:40])
                company_s = (job.get("company", "Company").replace(" ", "-")
                    .replace(",", "").replace("/", "-")[:25])
                pdf_name     = f"{title_s}-Navaneeta-Padmakumar-{company_s}.pdf"
                pdf_standard = os.path.join(job_dir, "resume_tailored.pdf")
                pdf_path     = os.path.join(job_dir, pdf_name)

                if cache_hit and copy_cluster_pdf(cluster, job_dir, pdf_name):
                    console.print(f"    [green]✓ Copied cluster PDF → {pdf_name}[/green]")
                else:
                    gen_tex(job_dir, compile_pdf=False)
                    tex_path = f"{job_dir}/resume_tailored.tex"
                    subprocess.run(
                        ["pdflatex", "-interaction=nonstopmode",
                         "-output-directory", job_dir, tex_path],
                        capture_output=True, text=True, timeout=30
                    )
                    if os.path.exists(pdf_standard):
                        shutil.copy(pdf_standard, pdf_path)
                        console.print(f"    [green]✓ Saved as {pdf_name}[/green]")
                        if cluster:
                            save_cluster_pdf(cluster, pdf_standard)
                    if os.path.exists(pdf_path):
                        console.print("    [green]✓ PDF compiled → resume_tailored.pdf[/green]")
                    else:
                        console.print("    [yellow]⚠ PDF compile failed — .tex saved, check manually[/yellow]")
            except FileNotFoundError:
                console.print("    [yellow]⚠ pdflatex not found — run: eval \"$(/usr/libexec/path_helper)\"[/yellow]")
            except Exception as e:
                console.print(f"    [yellow]⚠ PDF generation skipped: {e}[/yellow]")

        except Exception as e:
            console.print(f"    [red]Error: {e}[/red]")
            mark_applied(job["job_id"], status=3, notes=str(e))


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
    total     = len(easy_jobs) + len(full_jobs)

    if not total:
        console.print("[yellow]No jobs ready to auto-apply.[/yellow]")
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


def print_status():
    rows = get_all()
    if not rows:
        console.print("[yellow]No applications yet.[/yellow]")
        return

    status_map = {0: "Pending", 1: "✓ Applied", 2: "Skipped", 3: "Error"}
    color_map = {0: "white", 1: "green", 2: "yellow", 3: "red"}

    type_color = {"easy": "green", "full_form": "yellow", "unknown": "dim"}

    table = Table(title="Job Application Tracker", show_lines=True)
    table.add_column("Platform", style="cyan")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Posted", justify="right")
    table.add_column("Apply Type")
    table.add_column("Fit", justify="right")
    table.add_column("Claude Q", justify="right")
    table.add_column("Status")

    for r in rows:
        quality   = json.loads(r.get("resume_quality") or "{}")
        status    = r.get("applied", 0)
        atype     = r.get("apply_type") or "?"
        atype_str = f"[{type_color.get(atype, 'white')}]{atype}[/]"
        posted    = (r.get("date_posted") or "—")[-5:]  # show MM-DD only
        table.add_row(
            r["platform"].capitalize(),
            (r["title"] or "")[:30],
            (r["company"] or "")[:20],
            posted,
            atype_str,
            str(r.get("fit_score") or "—"),
            str(quality.get("overall") or "—"),
            f"[{color_map[status]}]{status_map[status]}[/]",
        )

    console.print(table)
    applied = sum(1 for r in rows if r.get("applied") == 1)
    skipped = sum(1 for r in rows if r.get("applied") == 2)
    pending = sum(1 for r in rows if r.get("applied") == 0)
    console.print(
        f"\n✓ Applied: {applied}  |  ⏳ Pending: {pending}  |  ⊘ Skipped: {skipped}"
    )


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
    parser.add_argument("--scrape",    action="store_true", help="Scrape new jobs")
    parser.add_argument("--classify",  action="store_true", help="Classify jobs as easy-apply or full-form")
    parser.add_argument("--process",   action="store_true", help="Run AI pipeline (tailor resume, cover letter, outreach)")
    parser.add_argument("--apply",     action="store_true", help="Auto-apply to pending jobs using generated resumes")
    parser.add_argument("--dry-run",   action="store_true", help="Simulate --apply without submitting (safe for testing)")
    parser.add_argument("--status",    action="store_true", help="Show application status table")
    parser.add_argument("--limit",     type=int, default=None, help="Max jobs to process per run")
    args = parser.parse_args()

    if args.status:
        print_status()
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
