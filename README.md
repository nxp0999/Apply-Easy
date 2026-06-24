# Apply Easy — Automated Job Application Pipeline

> **Stack:** Python · JobSpy · Greenhouse/Ashby/Lever APIs · Playwright · Groq (Llama 3) · Ollama · MLflow · Docker · Kubernetes · SQLite · Flask · React

---

## What This Does

Apply Easy is an end-to-end automated job application system. Given a LaTeX resume it:

1. **Scrapes** jobs from LinkedIn, Indeed, Naukri (via JobSpy) **and** 22 company career portals directly (Greenhouse, Ashby, Lever APIs) — targeting Flipkart, Razorpay, Atlassian, Databricks, Freshworks, etc.
2. **Filters** dead/irrelevant listings before any AI runs — ghost jobs, stale postings (>21 days), wrong location, off-target titles, blacklisted companies
3. **Scores** every surviving job 0–100 using deterministic rule-based scoring (zero LLM cost)
4. **Deep-evaluates** the top 10 jobs (score ≥ 75) with a Groq LLM: CV match table + 2 STAR interview stories per role
5. **Shows** a tiered shortlist with per-job gap mitigation tips (what to add to your resume for each role)
6. **Tailors** resume bullets per job, generates a cover letter and outreach email
7. **Renders** a PDF resume via Playwright/Chromium → A4 PDF (no pdflatex required)
8. **Auto-applies** via Playwright bots (LinkedIn Easy Apply, Indeed, Greenhouse, Lever, Ashby)
9. **Tracks** all experiments with MLflow — compare scoring thresholds across runs
10. **Runs unattended** as a Kubernetes CronJob (daily 9am UTC)

---

## Project Structure

```
Apply Easy/
├── Dockerfile                    <- Container image (Python + Playwright/Chromium)
├── docker-compose.yml            <- Pipeline + MLflow UI + Dashboard as services
├── Makefile                      <- make setup / run / prep / apply / status
├── run.sh                        <- Single-command install + run (no make needed)
├── k8s/                          <- Kubernetes manifests
│   ├── cronjob.yaml              <- Daily CronJob (9am UTC)
│   ├── mlflow-deployment.yaml    <- MLflow tracking server Deployment + Service
│   ├── configmap.yaml            <- Non-secret config
│   ├── storage.yaml              <- PersistentVolumeClaims (output + mlruns)
│   ├── namespace.yaml
│   └── secret.yaml.template      <- Fill in API keys, then apply
├── _local.py                     <- Secrets (gitignored)
├── config.py                     <- Thresholds, keywords, role clusters, paths
├── main.py                       <- Pipeline orchestrator + CLI
├── db.py                         <- SQLite schema, migrations, CRUD
├── dashboard.py                  <- Flask API (port 5050) + SSE log stream
├── generate_html_pdf.py          <- Playwright HTML → A4 PDF (replaces pdflatex)
├── resume_rules.py               <- LLM prompt builders (tailor, cover letter, outreach)
├── credentials.py                <- Fernet-encrypted session store
├── filters.py                    <- Pre-scoring gates (ghost job, stale, location, etc.)
├── scrapers/
│   ├── jobspy_scraper.py         <- LinkedIn / Indeed / Naukri via python-jobspy
│   └── ats_scraper.py            <- 22 companies via Greenhouse / Ashby / Lever APIs
├── pipeline/
│   ├── rule_scorer.py            <- Deterministic 0–100 fit scorer (zero LLM)
│   ├── deep_eval.py              <- LLM deep eval: CV match + STAR stories (top 10 jobs)
│   ├── experiment_tracker.py     <- MLflow: log params + metrics per --discover run
│   ├── tex_parser.py             <- my_resume.tex → clean plain text (BASE_RESUME)
│   ├── claude_tasks.py           <- Groq API: tailor, cover letter, outreach email
│   ├── ollama_tasks.py           <- Ollama local LLM: same tasks
│   ├── apply_detector.py         <- Classifies jobs: easy / full_form / unknown
│   ├── cluster_cache.py          <- Resume variant cache per role cluster
│   └── role_detector.py          <- Ranks top N roles from resume
├── applicator/
│   ├── base.py                   <- BaseApplicator + field inference
│   ├── linkedin.py               <- LinkedIn Easy Apply Playwright bot
│   ├── indeed.py                 <- Indeed Apply Playwright bot
│   └── ats/
│       ├── greenhouse.py         <- Greenhouse.io Playwright bot
│       ├── lever.py              <- Lever.co Playwright bot
│       └── ashby.py              <- Ashby HQ Playwright bot
├── chrome-extension/             <- MV3 extension for Workday / SmartRecruiters
└── output/                       <- Gitignored
    ├── applications.db
    ├── run.log
    └── applications/<job_id>/
        ├── resume_tailored.txt
        ├── <Title>-Navaneeta-<Company>.pdf
        ├── cover_letter.txt
        ├── outreach_email.txt
        └── fit_report.json
```

---

## Why Each Tool Was Chosen

| Tool | Used for | Why this tool |
|---|---|---|
| **python-jobspy** | Scrape LinkedIn / Indeed / Naukri | Single package covers all three India-facing job boards; no API keys required |
| **Greenhouse / Ashby / Lever APIs** | Scrape 22 company career portals directly | Public REST APIs return full JD text with zero scraping fragility; higher signal than board aggregators |
| **Playwright** | Browser automation (auto-apply) + PDF generation | Already required for auto-apply bots — reused for HTML→PDF to eliminate the 6.9GB pdflatex dependency |
| **Groq (Llama 3)** | LLM calls (tailor, cover letter, deep eval) | Free tier (100k tokens/day), fastest inference available; no GPU required |
| **Ollama** | Local LLM fallback | Unlimited usage, fully offline — useful when Groq rate limit is hit |
| **SQLite** | Job tracking database | Zero-config, single file, perfectly adequate for a personal pipeline; ships with Python |
| **MLflow** | Experiment tracking per `--discover` run | Tracks `avg_fit_score`, `strong_matches`, filter breakdowns across days — lets you tune `KEYWORD_PRESCORE_MIN` and `FIT_SCORE_THRESHOLD` with data instead of guessing |
| **Docker** | Container packaging | Playwright/Chromium has complex system library requirements; Docker makes setup a single command on any machine and removes the `pdflatex not found` class of errors |
| **Kubernetes** | Scheduled unattended runs | CronJob replaces fragile cron entries; `concurrencyPolicy: Forbid` prevents overlapping runs; PVC persists DB and MLflow data across pod restarts |
| **Flask** | Dashboard API + SSE log stream | Lightweight, zero boilerplate for a personal-use server; SSE support built-in |
| **Rich** | Terminal tables + progress bars | Makes the `--status` and `--discover` output readable without a browser |

---

## Quick Start

### Option A — Single command (installs everything, then runs)
```bash
bash run.sh
```
On first run: creates `.venv`, installs deps, installs Playwright Chromium, creates `_local.py` template.
Add your Groq key to `_local.py`, then run again.

### Option B — Make
```bash
make setup    # one-time install
make prep     # detect top 5 roles + write resume variants (run after resume changes)
make run      # scrape + score + shortlist  ← daily command
make apply    # apply to shortlisted jobs
make status   # view pipeline table
```

### Option C — Docker (no local Python setup)
```bash
# Start Docker Desktop first, then:
docker build -t apply-easy .
docker run --rm \
  -e GROQ_API_KEY=your_key \
  -v "$(pwd)/output:/app/output" \
  -v "$(pwd)/mlruns:/app/mlruns" \
  apply-easy --discover

# Full stack (pipeline + MLflow UI + dashboard)
GROQ_API_KEY=your_key docker-compose up
```

---

## Daily Workflow

```
my_resume.tex  ─(tex_parser)→  BASE_RESUME (plain text)

--prep   (run once, or after resume changes)
  role_detector → top 5 roles → resumes/<role>.txt  (edit manually per role)

--discover  (run daily)
  JobSpy + ATS portals → SQLite
  Pre-filters: ghost job / stale / blacklist / location / keyword prescore
  rule_scorer  → score 0–100 (zero LLM, instant, all jobs)
  deep_eval    → CV match + STAR stories via Groq (top 10 jobs ≥ 75 only)
  MLflow       → log run metrics to mlruns/mlflow.db
  print_status → tiered table + gap mitigation action items

--apply  (after reviewing shortlist)
  tailor_resume + cover_letter + outreach_email  (Groq)
  generate_html_pdf → Playwright/Chromium → A4 PDF
  applicator → LinkedIn / Indeed / Greenhouse / Lever / Ashby bots
```

---

## Scoring

### Tier 1 — Rule-based (all jobs, instant, $0)

| Dimension | Weight |
|---|---|
| Keyword overlap | 35% |
| Title match | 20% |
| Tech stack | 20% |
| Experience level | 15% |
| Location | 10% |
| Bonuses | MS degree +8, Databricks cert +5, modern tools +3, recency +5 |

### Tier 2 — LLM deep eval (top 10 jobs ≥ 75, ~$0.05 total)

- **CV match table**: each JD requirement → specific resume line (`strong / partial / gap`)
- **STAR stories**: 2 interview-ready stories drawn from real resume experience
- **Top selling point**: single strongest hire reason for that role

### Score tiers

| Score | Label | Action |
|---|---|---|
| 80–100 | Strong | Deep-evaluated, tailored, PDF generated, auto-applied |
| 70–79 | Good | Deep-evaluated, tailored, queued for apply |
| 55–69 | Moderate | Scored and listed — apply manually if interested |
| Below 55 | Weak | Skipped |

---

## Pre-Filters (applied before any scoring)

| Filter | What it drops |
|---|---|
| `is_blacklisted` | TCS, Infosys, Wipro, staffing firms |
| `is_off_target_title` | Trainer, sales, recruiter, SEO roles |
| `is_ghost_job` | JD contains "no longer accepting", "position filled", etc. |
| `is_stale_posting` | Posted more than 21 days ago |
| `is_overleveled` | Requires 6+ years experience |
| `is_wrong_location` | Non-India, non-remote |
| `keyword_prescore` | Less than 12% of candidate skills appear in JD |

---

## MLflow Experiment Tracking

Every `--discover` run logs to `mlruns/mlflow.db`:

```bash
# View dashboard
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5001
# Open http://localhost:5001
```

**Logged per run:**

| Type | Fields |
|---|---|
| Params | `keyword_prescore_min`, `fit_score_threshold`, `resume_mode`, `platforms` |
| Metrics | `jobs_scraped`, `jobs_filtered`, `jobs_scored`, `avg_fit_score`, `strong_matches`, `good_matches` |
| Metrics | `filtered_Wrong location`, `filtered_Low keyword match`, `filtered_Ghost job`, etc. |
| Artifacts | `top_jobs.txt`, `filter_breakdown.txt` |

Use the charts to tune thresholds: if `strong_matches` is always 0, lower `KEYWORD_PRESCORE_MIN`; if the shortlist is too noisy, raise it.

---

## Kubernetes (Unattended Cloud Deployment)

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/storage.yaml
kubectl apply -f k8s/configmap.yaml
# Copy k8s/secret.yaml.template → k8s/secret.yaml, fill base64 values
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/mlflow-deployment.yaml
kubectl apply -f k8s/cronjob.yaml

# Trigger a manual run immediately
kubectl create job --from=cronjob/apply-easy-discover test-run -n apply-easy
kubectl logs -f job/test-run -n apply-easy
```

The CronJob runs `--discover` daily at **9:00 AM UTC**. `concurrencyPolicy: Forbid` ensures runs never overlap.

---

## Configuration Reference

| Setting | Default | Description |
|---|---|---|
| `KEYWORD_PRESCORE_MIN` | `0.12` | Min fraction of candidate skills that must appear in JD |
| `FIT_SCORE_THRESHOLD` | `70` | Minimum rule-based score to proceed to tailoring |
| `CLUSTER_CACHE_DAYS` | `7` | Days before role-cluster resume cache expires |
| `HEADLESS` | `False` | `True` = headless browser for auto-apply |
| `JOB_SEARCH["location"]` | `"India"` | Primary scrape location |
| `JOB_SEARCH["hours_old"]` | `72` | Only scrape jobs posted in last N hours |
| `DEEP_EVAL_MIN` | `75` | Minimum score to trigger LLM deep evaluation |
| `DEEP_EVAL_LIMIT` | `10` | Max jobs to deep-evaluate per run |

---

## Applicator Coverage

| Platform | Method | Notes |
|---|---|---|
| LinkedIn | Playwright Easy Apply bot | Session saved (Fernet encrypted) |
| Indeed | Playwright Apply bot | Session saved |
| Greenhouse | Playwright bot | Stateless |
| Lever | Playwright bot | Stateless |
| Ashby | Playwright bot | Stateless |
| Workday / SmartRecruiters | Chrome Extension | Manual submit |

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError` | Use `.venv/bin/python main.py` or run `make setup` |
| `Cannot connect to Docker daemon` | Open Docker Desktop app, wait for menu-bar whale icon |
| `repository name must be lowercase` | Quote the volume path: `-v "$(pwd)/output:/app/output"` |
| `Pipeline already running` | Delete `output/pipeline.lock` if the previous PID is dead |
| Groq 429 rate limit | Switch `AI_MODE=ollama` in config or wait until midnight UTC |
| LinkedIn login loop | Delete `output/.credentials.enc`, re-run `--apply` |
| PDF not generated | Run `playwright install chromium` inside the venv |
| MLflow errors | Run `mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db` |
