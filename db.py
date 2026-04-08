import sqlite3
import json
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            platform         TEXT,
            job_id           TEXT UNIQUE,
            title            TEXT,
            company          TEXT,
            location         TEXT,
            apply_url        TEXT,
            scraped_at       TEXT,
            fit_score        INTEGER,
            fit_verdict      TEXT,
            fit_strengths    TEXT,
            fit_gaps         TEXT,
            tailored_resume  TEXT,
            resume_quality   TEXT,
            cover_letter     TEXT,
            outreach_subject TEXT,
            outreach_body    TEXT,
            rw_overall       INTEGER,
            rw_hard_skills   INTEGER,
            rw_soft_skills   INTEGER,
            rw_impact        INTEGER,
            rw_brevity       INTEGER,
            rw_style         INTEGER,
            rw_url           TEXT,
            rw_error         TEXT,
            rw_scored_at     TEXT,
            applied          INTEGER DEFAULT 0,
            applied_at       TEXT,
            notes            TEXT
        )
    """)
    conn.commit()
    conn.close()


def migrate_db():
    rw_columns = [
        ("rw_overall",     "INTEGER"),
        ("rw_hard_skills", "INTEGER"),
        ("rw_soft_skills", "INTEGER"),
        ("rw_impact",      "INTEGER"),
        ("rw_brevity",     "INTEGER"),
        ("rw_style",       "INTEGER"),
        ("rw_url",         "TEXT"),
        ("rw_error",       "TEXT"),
        ("rw_scored_at",   "TEXT"),
    ]
    conn = get_conn()
    existing = {row[1] for row in conn.execute("PRAGMA table_info(applications)").fetchall()}
    for col_name, col_type in rw_columns:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE applications ADD COLUMN {col_name} {col_type}")
    conn.commit()
    conn.close()


def job_exists(job_id: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM applications WHERE job_id=?", (job_id,)).fetchone()
    conn.close()
    return row is not None


def insert_job(job: dict):
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO applications
        (platform, job_id, title, company, location, apply_url, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        job["platform"], job["job_id"], job["title"],
        job["company"], job.get("location", ""), job.get("apply_url", ""),
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()


def update_claude_outputs(job_id, fit, tailored, quality, cover, outreach):
    conn = get_conn()
    conn.execute("""
        UPDATE applications SET
            fit_score        = ?,
            fit_verdict      = ?,
            fit_strengths    = ?,
            fit_gaps         = ?,
            tailored_resume  = ?,
            resume_quality   = ?,
            cover_letter     = ?,
            outreach_subject = ?,
            outreach_body    = ?
        WHERE job_id = ?
    """, (
        fit.get("score"), fit.get("verdict"),
        json.dumps(fit.get("strengths", [])),
        json.dumps(fit.get("gaps", [])),
        tailored,
        json.dumps(quality),
        cover,
        outreach.get("subject"), outreach.get("body"),
        job_id
    ))
    conn.commit()
    conn.close()


def update_rw_score(job_id: str, score):
    s = score.to_dict() if hasattr(score, "to_dict") else score
    conn = get_conn()
    conn.execute("""
        UPDATE applications SET
            rw_overall     = ?,
            rw_hard_skills = ?,
            rw_soft_skills = ?,
            rw_impact      = ?,
            rw_brevity     = ?,
            rw_style       = ?,
            rw_url         = ?,
            rw_error       = ?,
            rw_scored_at   = ?
        WHERE job_id = ?
    """, (
        s.get("overall"), s.get("hard_skills"), s.get("soft_skills"),
        s.get("impact"), s.get("brevity"), s.get("style"),
        s.get("url"), s.get("error"),
        datetime.utcnow().isoformat(), job_id,
    ))
    conn.commit()
    conn.close()


def mark_applied(job_id: str, status: int = 1, notes: str = ""):
    conn = get_conn()
    conn.execute("""
        UPDATE applications SET applied=?, applied_at=?, notes=? WHERE job_id=?
    """, (status, datetime.utcnow().isoformat(), notes, job_id))
    conn.commit()
    conn.close()


def get_pending(threshold: int = 0):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM applications
        WHERE applied = 0 AND fit_score >= ?
        ORDER BY fit_score DESC
    """, (threshold,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unscored():
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM applications
        WHERE tailored_resume IS NOT NULL
          AND tailored_resume != ''
          AND rw_overall IS NULL
          AND rw_error IS NULL
        ORDER BY fit_score DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM applications ORDER BY fit_score DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]