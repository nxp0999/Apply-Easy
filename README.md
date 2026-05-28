# Apply Easy — Automated Job Application Pipeline
### Powered by Groq (Llama 3.1) + Ollama (Mistral) + JobSpy + Playwright + pdflatex

---

## What This Does

Apply Easy is a fully automated job application pipeline that:

1. **Scrapes** job listings from LinkedIn and Indeed (India) via JobSpy
2. **Classifies** each job as Easy Apply, Full Form, or Unknown
3. **Scores** each job for fit against your resume using AI (0–100)
4. **Tailors** your resume bullets to match each job description
5. **Quality-checks** the tailored resume for factual accuracy and ATS strength
6. **Generates** a personalized cover letter per job
7. **Drafts** a cold outreach email to the hiring manager
8. **Generates** a `.tex` file in your exact Overleaf resume format
9. **Compiles** it to a pixel-perfect PDF using pdflatex (identical output to Overleaf)
10. **Tracks** every application in a local SQLite database with a live web dashboard
11. **Auto-applies** via Playwright browser automation (LinkedIn Easy Apply, Indeed, Naukri, Internshala) *(Phase 4 — in progress)*

---

## Project Structure

```
Apply Easy/
├── config.py                  <- Your resume, API keys, job keywords, thresholds
├── main.py                    <- Orchestrator — run this
├── db.py                      <- SQLite database layer
├── dashboard.py               <- Flask API server + React SPA host
├── generate_tex.py            <- Converts resume_tailored.txt to .tex (Overleaf format)
├── resume_rules.py            <- Canonical ATS rules, strong verbs, prompt builders
├── check_resume.py            <- Local ATS quality checker (simulation)
├── requirements.txt
├── scrapers/
│   ├── __init__.py
│   ├── jobspy_scraper.py      <- Unified scraper (LinkedIn + Indeed via JobSpy)
│   ├── naukri.py              <- Naukri scraper (wired in future phase)
│   └── internshala.py        <- Internshala scraper (wired in future phase)
├── pipeline/
│   ├── __init__.py
│   ├── claude_tasks.py        <- AI calls via Groq (fit score, tailor, cover letter, email)
│   ├── ollama_tasks.py        <- AI calls via Ollama local (same tasks, no rate limits)
│   └── apply_detector.py     <- Classifies jobs as easy / full_form / unknown
├── applicator/
│   ├── __init__.py
│   └── apply.py               <- Playwright auto-submit (Phase 4 — in progress)
├── apply-easy/                <- React frontend
│   ├── package.json
│   ├── public/
│   └── src/
│       ├── App.js             <- Root component
│       ├── App.css            <- Dark theme styles
│       ├── api.js             <- Fetch wrappers for /api/jobs and /api/stats
│       ├── StatsCards.js      <- Summary stat cards (6 metrics)
│       ├── FitScoreDistributionChart.js  <- ApexCharts bar chart
│       ├── JobsByPlatformChart.js        <- ApexCharts donut chart
│       └── ApplicationsTable.js         <- Sortable, filterable jobs table
└── output/
    ├── run.log                <- Full pipeline log (for cron debugging)
    ├── pipeline.lock          <- PID lock — prevents concurrent runs
    └── applications/
        └── <job_id>/
            ├── resume_tailored.txt      <- AI-tailored resume (plain text)
            ├── resume_tailored.tex      <- LaTeX version (your Overleaf template)
            ├── resume_tailored.pdf      <- Compiled PDF (identical to Overleaf output)
            ├── cover_letter.txt         <- Personalized cover letter
            ├── outreach_email.txt       <- Cold email (subject + body)
            └── fit_report.json          <- Fit score + resume quality breakdown
```

---

## Pipeline Design

```
+--------------------------------------------------------------------+
|                          APPLY EASY                                |
|                                                                    |
|  +----------+   +-----------+   +----------------------------+     |
|  |  SCRAPE  |-->| CLASSIFY  |-->|       AI PIPELINE          |     |
|  | JobSpy   |   | easy /    |   |                            |     |
|  | LinkedIn |   | full_form |   |  1. Fit Score              |     |
|  | Indeed   |   | unknown   |   |  2. Tailor Resume          |     |
|  +----------+   +-----------+   |  3. Resume QA Score        |     |
|                                 |  4. Cover Letter           |     |
|                                 |  5. Outreach Email         |     |
|                                 +-------------+--------------+     |
|                                               |                    |
|                                               v                    |
|                                  +------------------------+        |
|                                  |    PDF GENERATION      |        |
|                                  |  .txt -> .tex -> .pdf  |        |
|                                  |  (pdflatex, same as    |        |
|                                  |   Overleaf output)     |        |
|                                  +------------------------+        |
|                                               |                    |
|                                               v                    |
|                                  +------------------------+        |
|                                  |   AUTO-APPLY (Phase 4) |        |
|                                  |  (Playwright submit)   |        |
|                                  +------------------------+        |
+--------------------------------------------------------------------+
```

---

## Apply Type Classification

After scraping, each job is automatically classified into one of three types:

| Type | Meaning | Example platforms |
|---|---|---|
| `easy` | One-click apply (LinkedIn Easy Apply, Indeed) | LinkedIn, Indeed |
| `full_form` | External ATS form required | Greenhouse, Workday, Lever, Taleo, iCIMS |
| `unknown` | Could not determine reliably | Other or scraper-limited |

Classification uses four signals in order:
1. `easy_apply` boolean from JobSpy (most reliable)
2. `job_url_direct` domain matched against known ATS patterns
3. `apply_url` domain check
4. HTTP GET fallback to detect redirect targets

Run classification alone:
```bash
python3 main.py --classify
```

---

## AI Modes

The pipeline supports two AI backends — selected via the `AI_MODE` config or `AI_MODE` environment variable:

| Mode | Provider | Model | Rate limit | Best for |
|---|---|---|---|---|
| `groq` | Groq cloud | llama-3.1-8b-instant | 100k tokens/day free | Speed |
| `ollama` | Your Mac | Mistral 7B | None (unlimited) | Volume |

Set the mode via environment variable (required for cron):
```bash
export AI_MODE=ollama   # or groq
```

Or set `AI_MODE = "ollama"` in `config.py`. The env var takes precedence.

---

## Cron / Unattended Operation

The pipeline is fully cron-safe:

- **No interactive prompts** — AI mode is read from env/config, not stdin
- **PID lock file** (`output/pipeline.lock`) — prevents overlapping cron runs
- **Run log** (`output/run.log`) — every run appends structured log lines

Example cron entry (runs every 6 hours):
```cron
0 */6 * * * cd "/Users/apple/Desktop/My Projects/Apply Easy" && \
  AI_MODE=ollama .venv/bin/python3 main.py >> output/run.log 2>&1
```

---

## Setup — Step by Step

### Prerequisites
- Mac (Apple Silicon M-series recommended)
- Python 3.13+
- Homebrew installed
- A Google account (for Groq signup)

---

### Step 1 — Verify Python
```bash
python3 --version      # Should be 3.13+
pip3 --version
which python3
```

---

### Step 2 — Navigate to project folder
```bash
cd "/Users/apple/Desktop/My Projects/Apply Easy"
```

---

### Step 3 — Create and activate virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
# Prompt changes to: (.venv) apple@Mac Apply Easy %
```

> **Note:** If you use conda, deactivate the base environment first to avoid conflicts:
> ```bash
> conda deactivate
> source .venv/bin/activate
> ```

---

### Step 4 — Install Python dependencies
```bash
pip install flask flask-cors jobspy groq ollama \
            requests beautifulsoup4 playwright \
            rich lxml pdfplumber
```

---

### Step 5 — Install Playwright browser
```bash
playwright install chromium
```

---

### Step 6 — Install MacTeX (for pdflatex PDF compilation)
```bash
brew install --cask mactex-no-gui
```
This downloads ~6.9GB. When prompted for your password, enter it and wait for completion.
After install, activate pdflatex without restarting terminal:
```bash
eval "$(/usr/libexec/path_helper)"
pdflatex --version   # Should show: pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)
```

---

### Step 7 — Install Ollama (for unlimited local AI)
Download from https://ollama.com/download, install the Mac app, then:
```bash
ollama pull mistral
# Downloads ~4.1GB Mistral 7B model
```

---

### Step 8 — Set API keys
```bash
# Groq (free — get key at https://console.groq.com/keys)
export GROQ_API_KEY="your-groq-key-here"

# Make permanent
echo 'export GROQ_API_KEY="your-groq-key-here"' >> ~/.zshrc

# Activate pdflatex in every new session automatically
echo 'eval "$(/usr/libexec/path_helper)"' >> ~/.zshrc
```

---

### Step 9 — Configure config.py
```bash
open -e config.py
```
Fill in:
- `BASE_RESUME` — paste your full resume as plain text
- `JOB_SEARCH["keywords"]` — roles you want to target
- `AI_MODE` — `"groq"` or `"ollama"`
- `CREDENTIALS` — platform login details (or set as env vars below)

---

### Step 10 — Set platform credentials (for auto-apply)
```bash
export LINKEDIN_EMAIL="you@email.com"
export LINKEDIN_PASSWORD="yourpassword"
export INDEED_EMAIL="you@email.com"
export INDEED_PASSWORD="yourpassword"
export NAUKRI_EMAIL="you@email.com"
export NAUKRI_PASSWORD="yourpassword"
export INTERNSHALA_EMAIL="you@email.com"
export INTERNSHALA_PASSWORD="yourpassword"
```

---

### Step 11 — Build the React dashboard frontend
```bash
cd apply-easy
npm install
npm run build
cd ..
```

---

### Step 12 — Verify everything loads
```bash
.venv/bin/python3 -c "import config; print('Config OK')"
.venv/bin/python3 -c "import db; db.init_db(); print('DB OK')"
.venv/bin/python3 -c "from pipeline.claude_tasks import score_fit; print('Groq pipeline OK')"
.venv/bin/python3 -c "from pipeline.ollama_tasks import score_fit; print('Ollama pipeline OK')"
.venv/bin/python3 -c "from scrapers.jobspy_scraper import scrape_all; print('Scraper OK')"
pdflatex --version
```

---

### Step 13 — Test scraper
```bash
.venv/bin/python3 -c "
from scrapers.jobspy_scraper import scrape_all
jobs = scrape_all(max_jobs=3)
print(f'Got {len(jobs)} jobs')
print(jobs[0]['title'], '|', jobs[0]['company'])
"
```

---

### Step 14 — First full scrape + classify
```bash
python3 main.py --scrape
python3 main.py --classify
```

---

### Step 15 — First full AI processing run
```bash
AI_MODE=ollama python3 main.py --process
# Or with a limit to avoid rate limits:
AI_MODE=groq python3 main.py --process --limit 10
```

---

### Step 16 — Generate .tex and PDF resumes
```bash
# Generate .tex files in your Overleaf template format for all jobs
python3 generate_tex.py

# Compile all to PDF using pdflatex (exact Overleaf output, same fonts)
python3 generate_tex.py --compile

# Or compile a single job manually
pdflatex -interaction=nonstopmode \
  -output-directory output/applications/<job_id> \
  output/applications/<job_id>/resume_tailored.tex
```

---

### Step 17 — Check status table
```bash
python3 main.py --status
```

---

### Step 18 — Launch the live dashboard
Open a second terminal tab:
```bash
cd "/Users/apple/Desktop/My Projects/Apply Easy"
source .venv/bin/activate
python3 dashboard.py
```
Then open http://localhost:8765 in your browser.

Dashboard features:
- **6 stat cards**: Total, Pending, Applied, Skipped, Easy Apply count, Avg Fit Score
- **Fit score distribution** bar chart (ApexCharts)
- **Jobs by platform** donut chart (ApexCharts)
- **Applications table**: sortable by any column, search by title/company, filter by status and apply type
- Color-coded fit scores (green ≥70, yellow ≥50, red <50)
- Apply Type badges (Easy Apply = green, Full Form = yellow)
- Direct apply links

---

## Daily Usage — CLI Commands

### Re-activate venv (every new terminal session)
```bash
cd "/Users/apple/Desktop/My Projects/Apply Easy"
conda deactivate           # if conda base is active
source .venv/bin/activate
eval "$(/usr/libexec/path_helper)"   # activate pdflatex
```

### Run the full pipeline
```bash
AI_MODE=ollama python3 main.py
```

### Run steps individually
```bash
python3 main.py --scrape          # Scrape new jobs
python3 main.py --classify        # Classify easy / full_form / unknown
python3 main.py --process         # AI pipeline (score, tailor, cover letter, email)
python3 main.py --apply           # Auto-apply to qualified Easy Apply jobs
python3 main.py --status          # Status table in terminal
```

### Generate PDFs from processed resumes
```bash
python3 generate_tex.py              # All jobs -> .tex files
python3 generate_tex.py --compile    # All jobs -> .tex + .pdf via pdflatex
python3 generate_tex.py --job <id>   # Single job only
```

### Launch dashboard
```bash
python3 dashboard.py
# Open http://localhost:8765
```

### Reset errored jobs and retry
```bash
python3 -c "
import sqlite3
from config import DB_PATH
conn = sqlite3.connect(DB_PATH)
conn.execute(\"UPDATE applications SET applied=0, notes='' WHERE applied=3 AND fit_score IS NULL\")
conn.commit()
print('Reset', conn.total_changes, 'jobs')
conn.close()
"
python3 main.py --process
```

### Recommended first-run order
```bash
python3 main.py --scrape           # 1. Collect jobs
python3 main.py --classify         # 2. Classify apply types
AI_MODE=ollama python3 main.py --process  # 3. AI generates all materials
python3 generate_tex.py --compile  # 4. Compile PDFs
python3 main.py --status           # 5. Review in terminal
python3 dashboard.py               # 6. Review visually at http://localhost:8765
python3 main.py --apply            # 7. Auto-apply (Phase 4)
```

---

## Key Configuration Options (config.py)

| Setting | Default | What it does |
|---|---|---|
| AI_MODE | "ollama" | "groq" or "ollama" — overridden by AI_MODE env var |
| FIT_SCORE_THRESHOLD | 65 | Jobs below this score are skipped |
| RESUME_SIMILARITY_MIN | 70 | Min quality score for tailored resume |
| AUTO_APPLY | False | Set True to enable auto-submission |
| HEADLESS | True | Set False to watch browser in real time |
| max_per_platform | 10 | Max jobs scraped per keyword |

---

## Output Files

Every job that passes the fit threshold gets its own folder:

```
output/applications/<job_id>/
├── resume_tailored.txt       <- AI-tailored resume (plain text source)
├── resume_tailored.tex       <- LaTeX in your exact Overleaf template
├── resume_tailored.pdf       <- Compiled PDF (pdflatex, same as Overleaf)
├── cover_letter.txt          <- Personalized cover letter
├── outreach_email.txt        <- Cold email to hiring manager (subject + body)
└── fit_report.json           <- Fit score + resume quality breakdown
```

---

## Status Table Columns

| Column | What it means |
|---|---|
| Platform | linkedin / indeed |
| Apply Type | easy / full_form / unknown (color-coded badge) |
| Fit | AI fit score (0–100) against your resume |
| Claude Q | Quality score of the tailored resume (from resume_quality JSON) |
| Status | Pending / Applied / Skipped / Error (color-coded badge) |
| Link | Direct apply URL |

---

## AI Models Used

| Task | Groq mode | Ollama mode | Cost |
|---|---|---|---|
| Fit scoring | llama-3.1-8b-instant | mistral 7B | Free |
| Resume tailoring | llama-3.1-8b-instant | mistral 7B | Free |
| Resume QA | llama-3.1-8b-instant | mistral 7B | Free |
| Cover letter | llama-3.1-8b-instant | mistral 7B | Free |
| Outreach email | llama-3.1-8b-instant | mistral 7B | Free |
| PDF compilation | pdflatex (MacTeX) | pdflatex (MacTeX) | Free |

---

## Roadmap

| Phase | Feature | Status |
|---|---|---|
| Phase 1 | Cron safety (lock file, logging, no interactive prompts) | Done |
| Phase 2 | PDF output (pdflatex, Summary section, correct section order) | Done |
| Phase 3 | Apply type classification (easy / full_form / unknown) | Done |
| Phase 4a | LinkedIn Easy Apply automation (Playwright) | Planned |
| Phase 4b | Indeed Easy Apply automation (Playwright) | Planned |
| Phase 4c | Greenhouse ATS form automation | Planned |
| Phase 4d | Workday ATS form automation | Planned |
| Phase 5 | Full cron job with email digest of results | Planned |

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `(.venv)` not showing | Run `source .venv/bin/activate` from project root |
| Both `(base)` and `(.venv)` active | Run `conda deactivate` first, then activate `.venv` |
| `ModuleNotFoundError: flask` | Use `.venv/bin/python3 dashboard.py` or `conda deactivate` first |
| `ModuleNotFoundError` for any package | Make sure `.venv` is active; re-run `pip install` |
| pdflatex not found | Run `eval "$(/usr/libexec/path_helper)"` or restart terminal |
| Groq 429 token limit | Resets at midnight UTC (5:30 AM IST); switch to `AI_MODE=ollama` |
| Groq 429 mid-run | Reset errored jobs (see above); retry or use second Groq account |
| Scraper returns 0 jobs | Old bs4 scrapers are blocked; use `jobspy_scraper.py` |
| JobSpy rate-limited | Wait 5 min and retry; reduce `max_per_platform` in config |
| Ollama JSON errors | Robust `_parse_json` handles this; retry if it persists |
| `(Action Verb: X)` in resume | Fixed by `_clean_model_output()` in main.py; update and re-run `--process` |
| Hallucinated metrics in email | Anti-hallucination rule added to `build_outreach_prompt` in resume_rules.py |
| PDF missing Summary section | Fixed in generate_tex.py — `render_summary()` renders prose block |
| Wrong section order in PDF | Fixed — order is Summary → Skills → Experience → Projects → Education → Certs |
| Playwright login fails | Set `HEADLESS=False` in config.py to debug visually |
| MacTeX install cancelled | Re-run `brew install --cask mactex-no-gui` and enter password when asked |
| pdflatex compile error | Upload `.tex` to Overleaf to see the exact LaTeX error |
| Dashboard shows blank page | Build the React app first: `cd apply-easy && npm install && npm run build` |
| VS Code Pylance warnings | Cmd+Shift+P → "Python: Select Interpreter" → `./.venv/bin/python` |

---

## Groq Rate Limits (Free Tier)

| Model | Requests/min | Tokens/min | Tokens/day |
|---|---|---|---|
| llama-3.1-8b-instant | 30 | 20,000 | 100,000 |
| llama-3.3-70b-versatile | 30 | 32,000 | 100,000 |

At ~5 API calls and ~2,500 tokens per job, you can process roughly 40 jobs/day free.
Switch to Ollama (Mistral 7B) with `AI_MODE=ollama` for unlimited local processing.

---

## Ollama Local AI

Runs fully on your Mac — no internet, no API key, no rate limits.

| Spec | Value |
|---|---|
| Model | Mistral 7B |
| RAM required | 8GB minimum, 16GB recommended |
| Speed (M-series Mac) | ~30–60 seconds per job |
| Quality vs Groq | Slightly lower, very close for resume tasks |

---

## Additional Utility Scripts

### Process with --limit
Process only N jobs per run to avoid hitting Groq token limits:

```bash
python3 main.py --process --limit 10
```

### Wipe everything and start fresh
```bash
python3 main.py --reset
# Type 'yes' to confirm — deletes DB and all output files
```

### Restore scores from output files
If scores get wiped from the DB but output files still exist on disk,
restore them without re-running any AI:

```bash
python3 -c "
import sqlite3, os, json
from config import DB_PATH, OUTPUT_DIR

conn = sqlite3.connect(DB_PATH)
restored = 0

rows = conn.execute('SELECT job_id FROM applications WHERE fit_score IS NULL').fetchall()
for (job_id,) in rows:
    fit_path = os.path.join(OUTPUT_DIR, job_id, 'fit_report.json')
    resume_path = os.path.join(OUTPUT_DIR, job_id, 'resume_tailored.txt')
    if os.path.exists(fit_path) and os.path.exists(resume_path):
        with open(fit_path) as f:
            data = json.load(f)
        fit = data.get('fit', {})
        score = fit.get('score')
        if score:
            conn.execute('UPDATE applications SET fit_score=? WHERE job_id=?', (score, job_id))
            restored += 1

conn.commit()
conn.close()
print(f'Restored scores for {restored} jobs from output files')
"
```

---

## Score Ranges Guide

| Score | Meaning | Action |
|---|---|---|
| 85–100 | Strong match | Apply immediately |
| 70–84 | Good match | Apply with tailored resume |
| 65–69 | Marginal | Review manually before applying |
| Below 65 | Weak match | Skipped automatically |

---

*Built with JobSpy, Groq (Llama 3.1 8B), Ollama (Mistral 7B), pdflatex (MacTeX), Flask, React, ApexCharts, Playwright, SQLite, and Rich.*
