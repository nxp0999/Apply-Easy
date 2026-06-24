#!/usr/bin/env python3
"""
dashboard.py
Flask server that exposes the SQLite DB as a REST API and serves
the React frontend from apply-easy/build/.

Run:
    python dashboard.py
    open http://localhost:8765
"""

import glob
import os
import sqlite3
import subprocess
import time

from flask import Flask, Response, jsonify, request, send_file, send_from_directory, stream_with_context
from flask_cors import CORS

from config import DB_PATH, OUTPUT_DIR, PROFILE

LOG_PATH = "output/run.log"

BUILD_DIR = os.path.join(os.path.dirname(__file__), "apply-easy", "build")

app = Flask(__name__, static_folder=BUILD_DIR, static_url_path="")
CORS(app)  # allow React dev-server (port 3000) to call our API


# ── helpers ───────────────────────────────────────────────────────────────

def _query(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _query_one(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else {}


# ── API endpoints ──────────────────────────────────────────────────────────

@app.route("/api/jobs")
def api_jobs():
    jobs = _query("SELECT * FROM applications ORDER BY fit_score DESC")
    return jsonify(jobs)


@app.route("/api/stats")
def api_stats():
    stats = _query_one("""
        SELECT
            COUNT(*)                                                   AS total,
            SUM(CASE WHEN applied = 1 THEN 1 ELSE 0 END)              AS applied,
            SUM(CASE WHEN applied = 2 THEN 1 ELSE 0 END)              AS skipped,
            SUM(CASE WHEN applied = 0 THEN 1 ELSE 0 END)              AS pending,
            ROUND(AVG(CASE WHEN fit_score > 0 THEN fit_score END), 1) AS avg_fit,
            SUM(CASE WHEN apply_type = 'easy'      THEN 1 ELSE 0 END) AS easy_apply,
            SUM(CASE WHEN apply_type = 'full_form' THEN 1 ELSE 0 END) AS full_form
        FROM applications
    """)
    return jsonify(stats)


@app.route("/api/jobs/<job_id>")
def api_job(job_id):
    rows = _query("SELECT * FROM applications WHERE job_id = ?", (job_id,))
    if not rows:
        return jsonify({"error": "not found"}), 404
    return jsonify(rows[0])


@app.route("/api/logs")
def api_logs():
    """SSE stream: sends last 80 lines of run.log then follows new output."""
    def generate():
        os.makedirs("output", exist_ok=True)
        if not os.path.exists(LOG_PATH):
            open(LOG_PATH, "w").close()
        with open(LOG_PATH, "r") as f:
            lines = f.readlines()
            for line in lines[-80:]:
                yield f"data: {line.rstrip()}\n\n"
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    time.sleep(0.4)
                    yield ": keepalive\n\n"
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/profile")
def api_profile():
    """Expose applicant profile for the Chrome extension form-filler."""
    return jsonify(PROFILE)


@app.route("/api/pending-jobs")
def api_pending_jobs():
    """All jobs with generated materials not yet applied — for extension popup."""
    jobs = _query("""
        SELECT job_id, platform, title, company, location,
               apply_url, apply_url_direct, fit_score, apply_type,
               date_posted, salary_min, salary_max
        FROM applications
        WHERE tailored_resume IS NOT NULL
          AND applied = 0
        ORDER BY fit_score DESC
        LIMIT 100
    """)
    return jsonify(jobs)


@app.route("/api/job-by-url")
def api_job_by_url():
    """Find the best-matching DB job for a given page URL (used by content.js)."""
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url param required"}), 400
    # strip query params for matching
    base = url.split("?")[0]
    rows = _query("""
        SELECT * FROM applications
        WHERE (apply_url      LIKE ? OR apply_url_direct LIKE ?)
          AND applied = 0
        ORDER BY fit_score DESC
        LIMIT 1
    """, (f"%{base}%", f"%{base}%"))
    if rows:
        return jsonify(rows[0])
    return jsonify({"error": "not found"}), 404


@app.route("/api/pdf/<job_id>")
def api_pdf(job_id):
    """Serve the tailored PDF for a job (extension uploads it to file inputs)."""
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    # Try named PDF first, fall back to resume_tailored.pdf
    named = sorted(glob.glob(os.path.join(job_dir, "*.pdf")))
    named = [p for p in named if "tailored" not in os.path.basename(p) or p.endswith("resume_tailored.pdf")]
    pdf_path = named[0] if named else os.path.join(job_dir, "resume_tailored.pdf")
    if not os.path.exists(pdf_path):
        return jsonify({"error": "pdf not found"}), 404
    return send_file(pdf_path, mimetype="application/pdf",
                     as_attachment=True,
                     download_name=os.path.basename(pdf_path))


@app.route("/api/fill-field", methods=["POST"])
def api_fill_field():
    """Ask Ollama/Claude to generate an answer for a specific form field."""
    data    = request.get_json(force=True)
    label   = data.get("label", "")
    job_id  = data.get("job_id", "")
    context = data.get("context", "")

    row = _query_one("SELECT * FROM applications WHERE job_id=?", (job_id,))
    if not row:
        return jsonify({"error": "job not found"}), 404

    try:
        from config import BASE_RESUME
        prompt = f"""You are filling a job application form field.

Job: {row.get('title','')} at {row.get('company','')}
Field label: "{label}"
Page context: {context}

Candidate background:
{BASE_RESUME[:1800]}

Rules:
- Answer ONLY the field described by the label
- Use specific numbers and achievements from the candidate background
- Never fabricate metrics not in the background above
- Keep answer under 120 words
- Write in first person, professional tone
- Output ONLY the answer text, nothing else"""

        from pipeline.ollama_tasks import _call
        answer = _call(prompt).strip()
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mark-applied/<job_id>", methods=["POST"])
def api_mark_applied(job_id):
    """Mark a job as applied (called by extension after form submit)."""
    data  = request.get_json(force=True) or {}
    notes = data.get("notes", "Applied via Chrome extension")
    conn  = sqlite3.connect(DB_PATH)
    from datetime import datetime
    conn.execute(
        "UPDATE applications SET applied=1, applied_at=?, notes=? WHERE job_id=?",
        (datetime.utcnow().isoformat(), notes, job_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/run/<cmd>", methods=["POST"])
def api_run(cmd):
    """Trigger a pipeline step in the background."""
    allowed = {"scrape", "classify", "process", "apply", "dry-run"}
    if cmd not in allowed:
        return jsonify({"error": "unknown command"}), 400
    subprocess.Popen(
        ["python", "main.py", f"--{cmd}"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    return jsonify({"started": cmd})


# ── Serve React SPA ────────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    # Serve static assets (JS, CSS, images) if they exist in the build dir
    if path and os.path.isfile(os.path.join(BUILD_DIR, path)):
        return send_from_directory(BUILD_DIR, path)
    # Fall back to index.html for all other routes (React router)
    index = os.path.join(BUILD_DIR, "index.html")
    if os.path.isfile(index):
        return send_from_directory(BUILD_DIR, "index.html")
    return (
        "<h2>Frontend not built yet.</h2>"
        "<p>Run: <code>cd apply-easy && npm install && npm run build</code></p>",
        200,
    )


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  Apply Easy Dashboard")
    print("  Running at http://localhost:8765\n")
    app.run(host="0.0.0.0", port=8765, debug=False)
