import json
import re
import ollama
from config import BASE_RESUME

MODEL = "mistral"


def _call(prompt: str) -> str:
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1},
    )
    return response["message"]["content"].strip()


def _parse_json(text: str) -> dict:
    # Strip markdown fences
    text = re.sub(r"```json|```", "", text).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        pass

    # Find outermost { } block
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found: {text[:300]}")

    raw = text[start:end+1]

    # Fix common Mistral issues
    raw = re.sub(r",\s*([}\]])", r"\1", raw)           # trailing commas
    raw = re.sub(r':\s*"(\d+)"', lambda m: f": {m.group(1)}", raw)  # "95" → 95
    raw = re.sub(r':\s*"true"',  ": true",  raw, flags=re.IGNORECASE)
    raw = re.sub(r':\s*"false"', ": false", raw, flags=re.IGNORECASE)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Mistral sometimes returns two JSON objects — take only the first
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(raw)
        return obj
    except Exception as e:
        raise ValueError(f"JSON parse failed: {e}\nRaw: {raw[:300]}")


def score_fit(job: dict) -> dict:
    prompt = f"""You are a technical recruiter. Rate this resume against the job.
Respond with ONLY a JSON object. No text before or after.

RESUME:
{BASE_RESUME}

JOB TITLE: {job.get('title', '')}
COMPANY: {job.get('company', '')}
JOB DESCRIPTION:
{job.get('description', '')}

JSON format:
{{
  "score": <integer 0-100>,
  "verdict": "<one line>",
  "strengths": ["<item1>", "<item2>"],
  "gaps": ["<item1>", "<item2>"]
}}"""
    return _parse_json(_call(prompt))


def tailor_resume(job: dict) -> str:
    prompt = f"""You are an expert ATS resume writer in 2026. Your job is to rewrite this resume
to maximize its ATS score for the specific job below. Follow every rule exactly.

═══════════════════════════════════════════════════════
ATS RULES — EVERY RULE IS MANDATORY
═══════════════════════════════════════════════════════

KEYWORD RULES:
- Extract ALL required and preferred skills from the job description
- Place the most critical JD keywords in: Summary, Skills section, AND first bullet of most recent role
- Use EXACT terminology from JD (e.g. if JD says "Natural Language Processing (NLP)", write it exactly that way)
- Aim to match 60-80% of keywords from the job description
- Weave keywords naturally into achievement bullets — never list them without context
- Mention the most important skills MORE THAN ONCE across different sections

BULLET RULES (most important for ATS score):
- Every bullet MUST follow: Action Verb + Task + Result (with a number)
- Action verbs must be strong and past-tense: Built, Designed, Implemented, Automated,
  Optimized, Reduced, Increased, Deployed, Led, Analyzed, Developed, Engineered, Achieved
- Every bullet MUST contain at least one specific metric, number, or percentage
- Use the EXACT numbers from the original resume — never remove or change them
- Bullets must be 1-2 lines maximum — cut anything longer
- NEVER use filler phrases: "responsible for", "helped with", "worked on",
  "demonstrating expertise", "showcasing ability", "passionate about", "driven by"

FORMATTING RULES (for ATS parsing):
- Single column layout only — no tables, no multi-column sections
- Standard section headers only: SUMMARY, EDUCATION, CERTIFICATIONS,
  TECHNICAL SKILLS, PROFESSIONAL EXPERIENCE, PROJECTS
- Contact info in body text, not header/footer
- Dates in consistent format: Month YYYY (e.g. July 2021)
- Reverse chronological order for experience and projects

STRUCTURE RULES:
- SUMMARY section: 3-4 lines, pack the most critical JD keywords here, mention the exact job title
- TECHNICAL SKILLS: mirror every keyword from JD that the candidate actually has,
  group by category, use the exact terms from the JD
- EXPERIENCE bullets: quantified impact in every single bullet
- PROJECTS: lead with most relevant to this JD, include tech stack in header

WHAT YOU MUST NEVER DO:
- Never fabricate experience, tools, metrics, or skills not in the original
- Never change company names, job titles, dates, or GPA
- Never remove a metric or number that exists in the original
- Never add filler phrases
- Never use tables or multi-column layouts
- Never output anything except the resume text

═══════════════════════════════════════════════════════
TARGET JOB
═══════════════════════════════════════════════════════
Title: {job.get('title', '')}
Company: {job.get('company', '')}

Job Description:
{job.get('description', '')[:2000]}

═══════════════════════════════════════════════════════
ORIGINAL RESUME — preserve all facts, numbers, and metrics exactly
═══════════════════════════════════════════════════════
{BASE_RESUME}

Now write the tailored resume. Output ONLY the resume text. Nothing else."""
    return _call(prompt)


def score_tailored_resume(tailored: str) -> dict:
    prompt = f"""You are a resume auditor. Compare tailored vs original resume.
Respond with ONLY a JSON object. No text before or after.

ORIGINAL:
{BASE_RESUME[:1500]}

TAILORED:
{tailored[:1500]}

JSON format:
{{
  "overall": <integer 0-100>,
  "factual_accuracy": <integer 0-100>,
  "ats_score": <integer 0-100>,
  "clarity": <integer 0-100>,
  "drift_warning": false,
  "notes": "<one sentence>"
}}"""
    return _parse_json(_call(prompt))


def generate_cover_letter(job: dict) -> str:
    prompt = f"""Write a cover letter for this job application.
Output ONLY the cover letter text, nothing else.

CANDIDATE:
{BASE_RESUME[:1500]}

JOB: {job.get('title', '')} at {job.get('company', '')}
DESCRIPTION: {job.get('description', '')[:800]}

3 paragraphs, under 250 words. Professional but human tone."""
    return _call(prompt)


def generate_outreach_email(job: dict) -> dict:
    prompt = f"""Write a cold outreach email for a job application.
Respond with ONLY a JSON object. No text before or after.

JOB: {job.get('title', '')} at {job.get('company', '')}
CANDIDATE SUMMARY: MS Computer Science UTD, 2.5 years experience, Python/ML/PySpark/Databricks

JSON format:
{{
  "subject": "<email subject line>",
  "body": "<email body 4-5 sentences>"
}}"""
    return _parse_json(_call(prompt))
