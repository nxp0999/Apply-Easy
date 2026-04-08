import argparse
import json
import os
from rich.console import Console
from rich.table import Table
from rich.progress import track

from config import (
    AI_MODE,
    PLATFORMS,
    FIT_SCORE_THRESHOLD,
    RESUME_SIMILARITY_MIN,
    AUTO_APPLY,
    OUTPUT_DIR,
)
from db import (
    init_db,
    migrate_db,
    insert_job,
    update_claude_outputs,
    mark_applied,
    get_pending,
    get_all,
    get_unscored,
    update_rw_score,
)

console = Console()


# ── STEP 1: SCRAPE ────────────────────────────────────────────────────────


def scrape_all():
    from scrapers.jobspy_scraper import scrape_all as _scrape

    all_jobs = _scrape()

    for job in all_jobs:
        insert_job(job)

    console.print(f"\n[green]✓ Scraped {len(all_jobs)} unique jobs.[/green]")
    return all_jobs


# ── STEP 2: CLAUDE PIPELINE ───────────────────────────────────────────────


# def process_with_claude(scraped_jobs):
# limit = 3  # for testing
def process_with_claude(scraped_jobs, limit=None):
    ai_mode = os.environ.get("AI_MODE", "groq")

    # Always use Groq for scoring (more accurate, small token usage)
    # Use selected mode for heavy generation tasks
    from pipeline.claude_tasks import score_fit, score_tailored_resume

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
    from config import AI_MODE
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

            # 2. Tailor resume
            tailored = tailor_resume(job)

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
            # Auto-generate .tex and compile to PDF
            try:
                from generate_tex import process_job as gen_tex
                from config import HEADLESS
                import subprocess
                job_dir = os.path.join(OUTPUT_DIR, job["job_id"])
                gen_tex(job_dir, compile_pdf=False)  # generate .tex
                tex_path = f"{job_dir}/resume_tailored.tex"
                pdf_path = f"{job_dir}/resume_tailored.pdf"
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode",
                     "-output-directory", job_dir, tex_path],
                    capture_output=True, text=True, timeout=30
                )
                # if result.returncode == 0:
            
                if os.path.exists(pdf_path):
                    console.print(f"    [green]✓ PDF compiled → resume_tailored.pdf[/green]")
                else:
                    console.print(f"    [yellow]⚠ PDF compile failed — .tex saved, check manually[/yellow]")
            except FileNotFoundError:
                console.print(f"    [yellow]⚠ pdflatex not found — run: eval \"$(/usr/libexec/path_helper)\"[/yellow]")
            except Exception as e:
                console.print(f"    [yellow]⚠ PDF generation skipped: {e}[/yellow]")

        except Exception as e:
            console.print(f"    [red]Error: {e}[/red]")
            mark_applied(job["job_id"], status=3, notes=str(e))


# ── STEP 3: RESUMEWORDED SCORING ──────────────────────────────────────────


def score_with_resumeworded():
    from pipeline.resumeworded import score_batch

    jobs = get_unscored()
    if not jobs:
        console.print("[yellow]No resumes pending ResumeWorded scoring.[/yellow]")
        return

    console.print(f"\n[cyan]Uploading {len(jobs)} resumes to ResumeWorded...[/cyan]")
    results = score_batch(jobs)

    for job_id, score in results.items():
        update_rw_score(job_id, score)
        s = score.to_dict()
        if s.get("error"):
            console.print(f"  [red]✗ {job_id}: {s['error']}[/red]")
        else:
            console.print(
                f"  [green]✓[/green] Score: [bold]{s['overall']}/100[/bold]  "
                f"(Impact: {s['impact']} | Brevity: {s['brevity']} | Style: {s['style']})"
            )
            job_dir = os.path.join(OUTPUT_DIR, job_id)
            if os.path.isdir(job_dir):
                with open(f"{job_dir}/resumeworded_score.json", "w") as f:
                    json.dump(s, f, indent=2)


# ── STATUS TABLE ──────────────────────────────────────────────────────────


def print_status():
    rows = get_all()
    if not rows:
        console.print("[yellow]No applications yet.[/yellow]")
        return

    status_map = {0: "Pending", 1: "✓ Applied", 2: "Skipped", 3: "Error"}
    color_map = {0: "white", 1: "green", 2: "yellow", 3: "red"}

    table = Table(title="Job Application Tracker", show_lines=True)
    table.add_column("Platform", style="cyan")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Fit", justify="right")
    table.add_column("Claude Q", justify="right")
    table.add_column("RW Score", justify="right")
    table.add_column("Status")

    for r in rows:
        quality = json.loads(r.get("resume_quality") or "{}")
        status = r.get("applied", 0)
        rw = r.get("rw_overall")
        rw_str = (
            f"[green]{rw}[/green]"
            if rw and rw >= 70
            else f"[yellow]{rw}[/yellow]"
            if rw
            else ("⚠ err" if r.get("rw_error") else "—")
        )
        table.add_row(
            r["platform"].capitalize(),
            (r["title"] or "")[:30],
            (r["company"] or "")[:20],
            str(r.get("fit_score") or "—"),
            str(quality.get("overall") or "—"),
            rw_str,
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

    # ── AI mode selector ──────────────────────────────────────────
    console.print("\n[bold cyan]Apply Easy — Job Automator[/bold cyan]")
    console.print("\nWhich AI mode do you want to use?")
    console.print("  [bold]1[/bold] — Groq API (fast, requires key, 100k tokens/day free)")
    console.print("  [bold]2[/bold] — Ollama local (unlimited, no API key, runs on your Mac)\n")

    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice == "1":
            console.print("[green]Using Groq API (llama-3.1-8b-instant)[/green]\n")
            if not os.getenv("GROQ_API_KEY"):
                console.print("[red]GROQ_API_KEY not set. Run: export GROQ_API_KEY='your-key'[/red]")
                return
            os.environ["AI_MODE"] = "groq"
            break
        elif choice == "2":
            console.print("[green]Using Ollama local (mistral)[/green]\n")
            os.environ["AI_MODE"] = "ollama"
            break
        else:
            console.print("[yellow]Please enter 1 or 2[/yellow]")
# ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="Apply Easy — Job Automator powered by Claude"
    )
    parser.add_argument("--scrape", action="store_true", help="Scrape new jobs")
    parser.add_argument("--process", action="store_true", help="Run Claude pipeline")
    parser.add_argument(
        "--score-rw", action="store_true", help="Upload to ResumeWorded"
    )
    #parser.add_argument("--status", action="store_true", help="Show tracker table")
    # New argument to show status without running other steps
    parser.add_argument("--status",   action="store_true", help="Show application status")
    parser.add_argument("--limit",    type=int, default=None, help="Max jobs to process per run")
    args = parser.parse_args()

    if args.status:
        print_status()
        return
    if args.scrape:
        scrape_all()
        return
    
    #if args.process:
    #    process_with_claude([])
    #    return 

    # Allow --process to accept an optional limit argument for testing
    if args.process:
        process_with_claude([], limit=args.limit)
        return
    
    if getattr(args, "score_rw", False):
        score_with_resumeworded()
        return

    # Default: full pipeline
    console.print("\n[bold cyan]🚀 Apply Easy — Full Pipeline[/bold cyan]\n")
    scraped = scrape_all()
    process_with_claude(scraped)
# Optional: allow --limit to apply to full pipeline run for testing
    process_with_claude(scraped, limit=args.limit)
    score_with_resumeworded()
    print_status()


if __name__ == "__main__":
    main()
