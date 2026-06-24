"""
pipeline/deep_eval.py

Hybrid deep evaluation for top-scoring jobs (rule score >= DEEP_EVAL_MIN).

Fires one Groq call per job that covers:
  Block B — CV match table (JD requirement → resume evidence)
  Block F — Two STAR stories tailored to the role

Output is stored in the DB fit_strengths / fit_gaps fields as enriched JSON
so print_status can surface it without re-calling the LLM.
"""

import json
import logging
import os

DEEP_EVAL_MIN   = 75   # only run on jobs scoring at or above this
DEEP_EVAL_LIMIT = 10   # max jobs to deep-eval per --discover run

_MODEL = "llama3-8b-8192"   # fast, free-tier friendly on Groq


def _build_prompt(job: dict, base_resume: str) -> str:
    title   = job.get("title", "")
    company = job.get("company", "")
    jd      = (job.get("description", "") or "")[:2000]
    resume  = base_resume[:2500]

    return f"""You are an expert career coach. Evaluate this candidate for the job below.

JOB: {title} at {company}
---
{jd}
---

CANDIDATE RESUME:
---
{resume}
---

Return ONLY valid JSON with exactly this structure:
{{
  "cv_match": [
    {{"requirement": "...", "evidence": "...", "strength": "strong|partial|gap"}}
  ],
  "star_stories": [
    {{"situation": "...", "task": "...", "action": "...", "result": "...", "relevance": "..."}}
  ],
  "overall_fit": "...",
  "top_selling_point": "..."
}}

Rules:
- cv_match: list 5-7 key JD requirements mapped to specific resume lines
- star_stories: exactly 2 stories drawn from real resume experience
- overall_fit: 1 sentence summary
- top_selling_point: the single strongest reason to hire this candidate for this role
- Output ONLY the JSON object, no prose before or after"""


def _call_groq(prompt: str) -> dict:
    from groq import Groq
    client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
    resp = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1200,
    )
    raw = resp.choices[0].message.content or ""
    # Strip markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def deep_eval_jobs(jobs: list[dict], base_resume: str) -> list[dict]:
    """
    Run deep eval on the supplied jobs (already filtered to score >= DEEP_EVAL_MIN).
    Returns the same list with 'deep_eval' key added to each job dict.
    """
    results = []
    for job in jobs[:DEEP_EVAL_LIMIT]:
        try:
            prompt = _build_prompt(job, base_resume)
            data   = _call_groq(prompt)
            job    = dict(job)
            job["deep_eval"] = data
            results.append(job)
            logging.info(f"deep_eval OK: {job.get('title')} @ {job.get('company')}")
        except Exception as exc:
            logging.warning(f"deep_eval failed for {job.get('job_id')}: {exc}")
            job = dict(job)
            job["deep_eval"] = {}
            results.append(job)
    return results


def format_deep_eval(data: dict) -> str:
    """Return a human-readable plain-text summary of deep_eval output."""
    if not data:
        return ""
    lines = []

    overall = data.get("overall_fit", "")
    top     = data.get("top_selling_point", "")
    if overall:
        lines.append(f"Fit: {overall}")
    if top:
        lines.append(f"Strongest point: {top}")

    cv_match = data.get("cv_match", [])
    if cv_match:
        lines.append("\nCV Match:")
        for row in cv_match:
            icon = {"strong": "✓", "partial": "~", "gap": "✗"}.get(row.get("strength", ""), "?")
            lines.append(f"  {icon} {row.get('requirement', '')} → {row.get('evidence', '')}")

    stars = data.get("star_stories", [])
    for idx, s in enumerate(stars, 1):
        lines.append(f"\nSTAR Story {idx} ({s.get('relevance', '')}):")
        lines.append(f"  S: {s.get('situation', '')}")
        lines.append(f"  T: {s.get('task', '')}")
        lines.append(f"  A: {s.get('action', '')}")
        lines.append(f"  R: {s.get('result', '')}")

    return "\n".join(lines)
