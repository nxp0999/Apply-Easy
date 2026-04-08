# Apply Easy — Automated Job Application Pipeline
### Powered by Groq (Llama 3.1) + Ollama (Mistral) + JobSpy + Playwright + pdflatex

---

## What This Does

Apply Easy is a fully automated job application pipeline that:

1. **Scrapes** job listings from LinkedIn and Indeed (India) via JobSpy
2. **Scores** each job for fit against your resume using AI (0–100)
3. **Tailors** your resume bullets to match each job description
4. **Quality-checks** the tailored resume for factual accuracy and ATS strength
5. **Generates** a personalized cover letter per job
6. **Drafts** a cold outreach email to the hiring manager
7. **Generates** a `.tex` file in your exact Overleaf resume format
8. **Compiles** it to a pixel-perfect PDF using pdflatex (identical output to Overleaf)
9. **Uploads** tailored resumes to ResumeWorded for independent scoring
10. **Tracks** every application in a local SQLite database with a live web dashboard
11. **Auto-applies** via Playwright browser automation (LinkedIn Easy Apply, Indeed, Naukri, Internshala)

---

## Project Structure

```
Apply Easy/
├── config.py                  <- Your resume, API keys, job keywords, thresholds
├── main.py                    <- Orchestrator — run this
├── db.py                      <- SQLite database layer
├── dashboard.py               <- Local web server for live dashboard
├── dashboard.html             <- Dashboard UI (charts, table, filters)
├── generate_tex.py            <- Converts resume_tailored.txt to .tex (Overleaf format)
├── generate_pdf.py            <- Converts resume_tailored.txt to .pdf (reportlab, no LaTeX)
├── requirements.txt
├── scrapers/
│   ├── __init__.py
│   ├── jobspy_scraper.py      <- Unified scraper (LinkedIn + Indeed via JobSpy)
│   ├── indeed.py              <- Legacy scraper (blocked, use jobspy_scraper instead)
│   ├── linkedin.py            <- Legacy scraper (blocked, use jobspy_scraper instead)
│   ├── naukri.py              <- Naukri scraper
│   └── internshala.py         <- Internshala scraper
├── pipeline/
│   ├── __init__.py
│   ├── claude_tasks.py        <- AI calls via Groq (fit score, tailor, cover letter, email)
│   ├── ollama_tasks.py        <- AI calls via Ollama local (same tasks, no rate limits)
│   └── resumeworded.py        <- ResumeWorded automation via Playwright
├── applicator/
│   ├── __init__.py
│   └── apply.py               <- Playwright auto-submit for all platforms
└── output/
    └── applications/
        └── <job_id>/
            ├── resume_tailored.txt      <- AI-tailored resume (plain text)
            ├── resume_tailored.tex      <- LaTeX version (your Overleaf template)
            ├── resume_tailored.pdf      <- Compiled PDF (identical to Overleaf output)
            ├── cover_letter.txt         <- Personalized cover letter
            ├── outreach_email.txt       <- Cold email (subject + body)
            ├── fit_report.json          <- Fit score + resume quality breakdown
            └── resumeworded_score.json  <- ResumeWorded score (overall + categories)
```

---

## Pipeline Design

```
+------------------------------------------------------------------+
|                         APPLY EASY                               |
|                                                                  |
|  +----------+   +----------+   +--------------------------+      |
|  |  SCRAPE  |-->|   DB     |-->|      AI PIPELINE         |      |
|  | JobSpy   |   | SQLite   |   |                          |      |
|  | LinkedIn |   |          |   |  1. Fit Score            |      |
|  | Indeed   |   |          |   |  2. Tailor Resume        |      |
|  +----------+   +----------+   |  3. Resume QA Score      |      |
|                                |  4. Cover Letter         |      |
|                                |  5. Outreach Email       |      |
|                                +------------+-------------+      |
|                                             |                    |
|                                             v                    |
|                                +------------------------+        |
|                                |    PDF GENERATION      |        |
|                                |  .txt -> .tex -> .pdf  |        |
|                                |  (pdflatex, same as    |        |
|                                |   Overleaf output)     |        |
|                                +------------+-----------+        |
|                                             |                    |
|                                             v                    |
|                                +------------------------+        |
|                                |  RESUMEWORDED SCORE    |        |
|                                |  (Playwright upload)   |        |
|                                +------------+-----------+        |
|                                             |                    |
|                                             v                    |
|                                +------------------------+        |
|                                |      AUTO-APPLY        |        |
|                                |  (Playwright submit)   |        |
|                                +------------------------+        |
+------------------------------------------------------------------+
```

---

## AI Modes

The pipeline supports two AI backends — switch between them at startup:

| Mode | Provider | Model | Rate limit | Best for |
|---|---|---|---|---|
| Groq API | Groq cloud | llama-3.1-8b-instant | 100k tokens/day free | Speed |
| Ollama local | Your Mac | Mistral 7B | None (unlimited) | Volume |

You are prompted to choose every time you run `python3 main.py`.

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
cd "/Users/apple/Desktop/Apply Easy"
```

---

### Step 3 — Create and activate virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
# Prompt changes to: (venv) (base) apple@Mac Apply Easy %
```

---

### Step 4 — Install Python dependencies
```bash
pip install anthropic requests beautifulsoup4 playwright rich lxml reportlab
pip install python-jobspy
pip install groq
pip install ollama
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

### Step 8 — Create project folder structure
```bash
mkdir -p scrapers pipeline applicator output/applications
touch scrapers/__init__.py pipeline/__init__.py applicator/__init__.py
```

---

### Step 9 — Set API keys
```bash
# Groq (free — get key at https://console.groq.com/keys)
export GROQ_API_KEY="your-groq-key-here"

# Make permanent
echo 'export GROQ_API_KEY="your-groq-key-here"' >> ~/.zshrc

# Activate pdflatex in every new session automatically
echo 'eval "$(/usr/libexec/path_helper)"' >> ~/.zshrc
```

---

### Step 10 — Configure config.py
```bash
open -e config.py
```
Fill in:
- BASE_RESUME — paste your full resume as plain text
- JOB_SEARCH["keywords"] — roles you want to target
- AI_MODE — "groq" or "ollama"
- CREDENTIALS — platform login details (or set as env vars below)

---

### Step 11 — Set platform credentials (for auto-apply)
```bash
export RESUMEWORDED_EMAIL="you@email.com"
export RESUMEWORDED_PASSWORD="yourpassword"
export LINKEDIN_EMAIL="you@email.com"
export LINKEDIN_PASSWORD="yourpassword"
export NAUKRI_EMAIL="you@email.com"
export NAUKRI_PASSWORD="yourpassword"
export INDEED_EMAIL="you@email.com"
export INDEED_PASSWORD="yourpassword"
export INTERNSHALA_EMAIL="you@email.com"
export INTERNSHALA_PASSWORD="yourpassword"
```

---

### Step 12 — Verify everything loads
```bash
python3 -c "import config; print('Config OK')"
python3 -c "import db; db.init_db(); print('DB OK')"
python3 -c "from pipeline.claude_tasks import score_fit; print('Groq pipeline OK')"
python3 -c "from pipeline.ollama_tasks import score_fit; print('Ollama pipeline OK')"
python3 -c "from scrapers.jobspy_scraper import scrape_all; print('Scraper OK')"
python3 -c "import main; print('main.py OK')"
pdflatex --version
```

---

### Step 13 — Test scraper
```bash
python3 -c "
from scrapers.jobspy_scraper import scrape_all
jobs = scrape_all(max_jobs=3)
print(f'Got {len(jobs)} jobs')
print(jobs[0]['title'], '|', jobs[0]['company'])
"
```

---

### Step 14 — Test AI pipeline on one job
```bash
python3 -c "
from pipeline.claude_tasks import score_fit
job = {
    'title': 'Data Scientist',
    'company': 'Flipkart',
    'description': 'Python, ML, PySpark, SQL experience required.'
}
fit = score_fit(job)
print('Score:', fit.get('score'))
print('Verdict:', fit.get('verdict'))
"
```

---

### Step 15 — First full scrape
```bash
python3 main.py --scrape
# Choose AI mode when prompted (1=Groq, 2=Ollama)
# Expected: 50-100 unique jobs scraped from LinkedIn + Indeed
```

---

### Step 16 — First full AI processing run
```bash
python3 main.py --process
# Choose 2 (Ollama) for unlimited processing with no rate limits
# Choose 1 (Groq) for faster but rate-limited processing
```

If Groq hits the daily 100k token limit mid-run, reset errored jobs and retry:
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

---

### Step 17 — Generate .tex and PDF resumes
```bash
# Generate .tex files in your Overleaf template format for all jobs
python3 generate_tex.py

# Compile all to PDF using pdflatex (exact Overleaf output, same fonts)
python3 generate_tex.py --compile

# Or compile a single job manually
pdflatex -interaction=nonstopmode \
  -output-directory output/applications/<job_id> \
  output/applications/<job_id>/resume_tailored.tex

# Open and review the PDF
open output/applications/<job_id>/resume_tailored.pdf
```

---

### Step 18 — Check status table
```bash
python3 main.py --status
```

---

### Step 19 — Launch the live dashboard
Open a second terminal tab:
```bash
cd "/pwd"
source venv/bin/activate
python3 dashboard.py
```
Then open http://localhost:8765 in your browser.

Dashboard features:
- Stat cards: total scraped, qualified, applied, avg fit score
- Fit score distribution bar chart
- Jobs by platform doughnut chart
- Filterable table: fit score bars, Claude Q, RW score, status, job links
- Auto-refreshes every 30 seconds

---

### Step 20 — Upload resumes to ResumeWorded
```bash
export RESUMEWORDED_EMAIL="you@email.com"
export RESUMEWORDED_PASSWORD="yourpassword"
python3 main.py --score-rw
```
Scores appear in the dashboard RW Score column (green >=70, yellow <70).

---

### Step 21 — Auto-apply via LinkedIn Easy Apply
```bash
export LINKEDIN_EMAIL="you@email.com"
export LINKEDIN_PASSWORD="yourpassword"
```

In config.py:
```python
AUTO_APPLY = True
HEADLESS   = False   # Watch it work first, then set True for headless
```

```bash
python3 main.py --apply
```

Always test with HEADLESS=False first to watch the browser and catch any issues.

---

## Daily Usage — CLI Commands

### Re-activate venv (every new terminal session)
```bash
cd "/Users/apple/Desktop/Apply Easy"
source venv/bin/activate
eval "$(/usr/libexec/path_helper)"   # activate pdflatex
```

### Run the full pipeline
```bash
python3 main.py
```

### Run steps individually
```bash
python3 main.py --scrape      # Scrape new jobs
python3 main.py --process     # AI pipeline (score, tailor, cover letter, email)
python3 main.py --score-rw    # Upload to ResumeWorded
python3 main.py --apply       # Auto-apply to qualified jobs
python3 main.py --status      # Status table in terminal
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
python3 main.py --process          # 2. AI generates all materials (choose Ollama)
python3 generate_tex.py --compile  # 3. Compile PDFs
python3 main.py --status           # 4. Review in terminal
python3 dashboard.py               # 5. Review visually at http://localhost:8765
python3 main.py --score-rw         # 6. ResumeWorded scores
python3 main.py --apply            # 7. Auto-apply
```

---

## Key Configuration Options (config.py)

| Setting | Default | What it does |
|---|---|---|
| AI_MODE | "ollama" | "groq" or "ollama" — overridden by startup prompt |
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
├── fit_report.json           <- Fit score + resume quality breakdown
└── resumeworded_score.json   <- ResumeWorded score (overall + categories)
```

---

## Status Table Columns

| Column | What it means |
|---|---|
| Fit | AI fit score (0-100) against your resume |
| Claude Q | Quality score of the tailored resume |
| RW Score | ResumeWorded independent score (green >=70) |
| Status | Pending / Applied / Skipped / Error |

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
| ResumeWorded scoring | Playwright automation | Playwright automation | Free |

---

## Troubleshooting

| Issue | Fix |
|---|---|
| (venv) not showing | Run source venv/bin/activate |
| ModuleNotFoundError | Make sure venv is active; re-run pip install |
| pdflatex not found | Run eval "$(/usr/libexec/path_helper)" or restart terminal |
| import time not defined | Move import time and import re to top of claude_tasks.py |
| zsh: parse error near '(' | Write files via cat > file.py << 'EOF' instead of text editor |
| Groq 429 token limit | Resets at midnight UTC (5:30 AM IST); switch to Ollama mode |
| Groq 429 mid-run | Reset errored jobs; re-run after reset or use second Groq account |
| Scraper returns 0 jobs | Old bs4 scrapers are blocked; use jobspy_scraper.py |
| JobSpy rate-limited | Wait 5 min and retry; reduce max_per_platform in config |
| Ollama JSON errors | Fixed by robust _parse_json in ollama_tasks.py; retry if persists |
| VS Code Pylance warnings | Cmd+Shift+P -> "Python: Select Interpreter" -> ./venv/bin/python |
| Dashboard parse error | Write dashboard.py via cat > dashboard.py << 'EOF' |
| Playwright login fails | Set HEADLESS=False in config.py to debug visually |
| MacTeX install cancelled | Re-run brew install --cask mactex-no-gui and enter password when asked |
| pdflatex compile error | Upload .tex to Overleaf to see the exact LaTeX error |

---

## Groq Rate Limits (Free Tier)

| Model | Requests/min | Tokens/min | Tokens/day |
|---|---|---|---|
| llama-3.1-8b-instant | 30 | 20,000 | 100,000 |
| llama-3.3-70b-versatile | 30 | 32,000 | 100,000 |

At ~5 API calls and ~2,500 tokens per job, you can process roughly 40 jobs/day free.
Switch to Ollama (Mistral 7B) for unlimited local processing with no rate limits.

---

## Ollama Local AI

Runs fully on your Mac — no internet, no API key, no rate limits.

| Spec | Value |
|---|---|
| Model | Mistral 7B |
| RAM required | 8GB minimum, 16GB recommended |
| Speed (M-series Mac) | ~30-60 seconds per job |
| Quality vs Groq | Slightly lower, very close for resume tasks |

Switch to Ollama anytime by choosing 2 at the startup prompt.

---

*Built with JobSpy, Groq (Llama 3.1 8B), Ollama (Mistral 7B), pdflatex (MacTeX), Playwright, SQLite, Rich, and Chart.js.*

---

## Additional Utility Scripts

### clean_unprocessed.py
Removes all unprocessed jobs (no fit score) from DB and output folders.
Keeps all jobs that have already been scored and processed.

```bash
python3 clean_unprocessed.py
```

Use this before a fresh scrape to avoid reprocessing old unscored jobs.

---

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

### Process with --limit
Process only N jobs per run to avoid hitting Groq token limits:

```bash
python3 main.py --process --limit 10
```

Recommended workflow when using Groq + Ollama hybrid mode:
- Groq handles fit scoring and resume QA (small, accurate calls)
- Ollama handles resume tailoring, cover letter, outreach email (large, unlimited)
- Choose mode 2 (Ollama) at startup — Groq scoring happens automatically

---

### Wipe everything and start fresh
```bash
python3 main.py --reset
# Type 'yes' to confirm — deletes DB and all output files
```

### Remove only unprocessed jobs (keep processed ones)
```bash
python3 clean_unprocessed.py
# Type 'yes' to confirm
```

### Recommended fresh scrape workflow
```bash
python3 clean_unprocessed.py          # 1. Remove unscored jobs
python3 main.py --scrape              # 2. Pull fresh jobs
python3 main.py --process --limit 10  # 3. Process in batches (choose mode 2)
python3 main.py --status              # 4. Review results
```

---

## Scoring Notes

### Why all scores look the same (95/100)
Ollama's Mistral 7B is generous with scores — it focuses on surface keyword
matches and doesn't penalize for seniority mismatches or missing tools.

Fix: Groq's Llama 3.1 8B is used automatically for scoring even in Ollama mode.
The pipeline is split:
- Scoring (fit + resume QA) → always uses Groq (accurate, ~500 tokens)
- Generation (tailor, cover letter, email) → uses selected mode

If scores still look inflated, the Groq key may not be set. Check:
```bash
echo $GROQ_API_KEY
export GROQ_API_KEY="your-key-here"
```

### Score ranges guide
| Score | Meaning | Action |
|---|---|---|
| 85–100 | Strong match | Apply immediately |
| 70–84 | Good match | Apply with tailored resume |
| 65–69 | Marginal | Review manually before applying |
| Below 65 | Weak match | Skipped automatically |
