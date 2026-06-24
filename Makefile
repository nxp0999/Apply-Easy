SHELL   := /bin/bash
VENV    := .venv
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

# ── Default target ────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

.PHONY: help setup run prep apply status clean-db

help:
	@echo ""
	@echo "  Apply Easy — Job Automator"
	@echo ""
	@echo "  First time:"
	@echo "    make setup      Install all dependencies (run once)"
	@echo ""
	@echo "  Daily workflow:"
	@echo "    make prep       Detect top roles + write resume variants (run after resume changes)"
	@echo "    make run        Scrape + score + shortlist jobs"
	@echo "    make apply      Apply to shortlisted jobs"
	@echo "    make status     View current job pipeline"
	@echo ""
	@echo "  Utilities:"
	@echo "    make clean-db   Wipe the job database and start fresh"
	@echo "    make dashboard  Start the web dashboard (localhost:5050)"
	@echo ""

# ── One-time setup ────────────────────────────────────────────────────────────
setup: $(VENV)/bin/activate _local.py
	@echo ""
	@echo "✓ Setup complete. Run:  make run"

$(VENV)/bin/activate: requirements.txt
	@echo "→ Creating virtual environment..."
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements.txt -q
	@echo "→ Installing Playwright browsers..."
	$(VENV)/bin/playwright install chromium --with-deps -q
	@touch $(VENV)/bin/activate

_local.py:
	@if [ ! -f _local.py ]; then \
		echo ""; \
		echo "  ⚠  Missing _local.py — creating template..."; \
		echo '# _local.py  (gitignored — put your real keys here)' > _local.py; \
		echo 'GROQ_API_KEY      = ""   # get free key at console.groq.com' >> _local.py; \
		echo 'ANTHROPIC_API_KEY = ""   # optional' >> _local.py; \
		echo 'EMAIL             = ""   # LinkedIn / Indeed login' >> _local.py; \
		echo 'PASSWORD          = ""' >> _local.py; \
		echo ""; \
		echo "  → Open _local.py and add your Groq API key, then run: make run"; \
		echo ""; \
	fi

# ── Daily commands ─────────────────────────────────────────────────────────────
prep:
	$(PYTHON) main.py --prep

run:
	$(PYTHON) main.py --discover

apply:
	$(PYTHON) main.py --apply

status:
	$(PYTHON) main.py --status

# ── Utilities ─────────────────────────────────────────────────────────────────
clean-db:
	@echo "Wiping output/applications.db..."
	@rm -f output/applications.db
	@echo "Done."

dashboard:
	$(PYTHON) dashboard.py
