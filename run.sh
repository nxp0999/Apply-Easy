#!/bin/bash
# run.sh — install all dependencies and run the job in one command
# Usage:  bash run.sh
#         bash run.sh prep        (detect roles + write resume variants)
#         bash run.sh apply       (apply to shortlisted jobs)
#         bash run.sh status      (view pipeline)

set -e

VENV=".venv"
PYTHON="$VENV/bin/python"
CMD="${1:-run}"   # default: discover + score

# ── 1. Python venv ────────────────────────────────────────────────────────────
if [ ! -f "$VENV/bin/activate" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"

# ── 2. Dependencies ───────────────────────────────────────────────────────────
echo "→ Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 3. Playwright browsers ────────────────────────────────────────────────────
if ! "$PYTHON" -c "from playwright.sync_api import sync_playwright; p = sync_playwright().__enter__(); p.chromium.executable_path; p.__exit__(None,None,None)" 2>/dev/null; then
    echo "→ Installing Playwright Chromium..."
    playwright install chromium --with-deps -q
fi

# ── 4. API key check ──────────────────────────────────────────────────────────
if [ ! -f "_local.py" ]; then
    echo ""
    echo "  ⚠  Missing _local.py — creating template..."
    cat > _local.py << 'EOF'
# _local.py  (gitignored — put your real keys here)
GROQ_API_KEY      = ""   # get a free key at console.groq.com
ANTHROPIC_API_KEY = ""   # optional
EMAIL             = ""   # LinkedIn / Indeed login email
PASSWORD          = ""
EOF
    echo "  → Open _local.py, add your Groq API key, then re-run: bash run.sh"
    echo ""
    exit 1
fi

GROQ_SET=$("$PYTHON" -c "
try:
    import _local
    print('yes' if getattr(_local, 'GROQ_API_KEY', '') else 'no')
except: print('no')
")
if [ "$GROQ_SET" = "no" ]; then
    echo ""
    echo "  ⚠  GROQ_API_KEY is empty in _local.py"
    echo "     Get a free key at https://console.groq.com and add it to _local.py"
    echo ""
    exit 1
fi

# ── 5. Run ────────────────────────────────────────────────────────────────────
echo ""
case "$CMD" in
    prep)   "$PYTHON" main.py --prep   ;;
    run)    "$PYTHON" main.py --discover ;;
    apply)  "$PYTHON" main.py --apply  ;;
    status) "$PYTHON" main.py --status ;;
    *)
        echo "Unknown command: $CMD"
        echo "Usage: bash run.sh [prep|run|apply|status]"
        exit 1
        ;;
esac
