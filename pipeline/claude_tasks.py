import os
import json
import re
import time
from groq import Groq
from config import BASE_RESUME

client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
MODEL  = "llama-3.1-8b-instant"


def _call(prompt: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            msg = str(e)
            if "rate_limit_exceeded" in msg:
                match = re.search(r"try again in (\d+)m([\d.]+)s", msg)
                wait = int(match.group(1)) * 60 + float(match.group(2)) if match else 60
                print(f"\n  [Rate limit] Waiting {int(wait)}s...")
                time.sleep(wait + 5)
            elif attempt < retries - 1:
                time.sleep(5)
            else:
                raise


def _parse_json(text: str) -> dict:
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON found: {text[:200]}")


def score_fit(job: dict) -> dict:
    prompt = f"""
You are an expert technical recruiter.
Rate how well this candidate's resume matches this job.
Respond ONLY with valid JSON, no markdown, no preamble.

RESUME:
{BASE_RESUME}

JOB TITLE: {job.get('title', '')}
COMPANY: {job.get('company', '')}
JOB DESCRIPTION:
{job.get('description', '')}

Return this exact JSON:
{{
  "score": <int 0-100>,
  "verdict": "<one line summary>",
  "strengths": ["<strength1>", "<strength2>"],
  "gaps": ["<gap1>", "<gap2>"]
}}
"""
    return _parse_json(_call(prompt))


def tailor_resume(job: dict) -> str:
    prompt = f"""You are an expert ATS resume writer in 2026. Rewrite this resume to maximize
its ATS score for the specific job below. Follow every rule exactly.

KEYWORD RULES:
- Extract ALL required and preferred skills from the job description
- Place critical JD keywords in: Summary, Skills section, AND first bullet of most recent role
- Use EXACT terminology from JD (e.g. if JD says "Natural Language Processing (NLP)", write it that way)
- Aim to match 60-80% of keywords from the job description
- Weave keywords naturally into achievement bullets, never list them without context
- Mention the most important skills MORE THAN ONCE across different sections

BULLET RULES:
- Every bullet MUST follow: Action Verb + Task + Result (with a number)
- Action verbs must be strong past-tense: Built, Designed, Implemented, Automated,
  Optimized, Reduced, Increased, Deployed, Led, Analyzed, Developed, Engineered, Achieved
- Every bullet MUST contain at least one specific metric, number, or percentage
- Use the EXACT numbers from the original resume, never remove or change them
- Bullets must be 1-2 lines maximum
- NEVER use: "responsible for", "helped with", "worked on", "demonstrating expertise",
  "showcasing ability", "passionate about", "driven by"

FORMATTING RULES:
- Single column layout only, no tables, no multi-column sections
- Standard section headers only: SUMMARY, EDUCATION, CERTIFICATIONS,
  TECHNICAL SKILLS, PROFESSIONAL EXPERIENCE, PROJECTS
- Dates in consistent format: Month YYYY (e.g. July 2021)
- Reverse chronological order for experience and projects

STRUCTURE RULES:
- SUMMARY: 3-4 lines, pack the most critical JD keywords here, mention the exact job title
- TECHNICAL SKILLS: mirror every keyword from JD the candidate actually has,
  group by category, use exact terms from the JD
- EXPERIENCE bullets: quantified impact in every single bullet
- PROJECTS: lead with most relevant to this JD, include tech stack in header

NEVER:
- Fabricate experience, tools, metrics, or skills not in the original
- Change company names, job titles, dates, or GPA
- Remove any metric or number that exists in the original
- Add filler phrases
- Output anything except the resume text

TARGET JOB:
Title: {job.get('title', '')}
Company: {job.get('company', '')}
Description:
{job.get('description', '')[:2000]}

ORIGINAL RESUME:
{BASE_RESUME}

Output ONLY the resume text. Nothing else."""
    return _call(prompt)


def score_tailored_resume(tailored: str) -> dict:
    prompt = f"""
You are a resume quality auditor.
Compare the TAILORED resume against the ORIGINAL resume.
Respond ONLY with valid JSON, no markdown, no preamble.

ORIGINAL RESUME:
{BASE_RESUME}

TAILORED RESUME:
{tailored}

Return this exact JSON:
{{
  "overall": <int 0-100>,
  "factual_accuracy": <int 0-100>,
  "ats_score": <int 0-100>,
  "clarity": <int 0-100>,
  "drift_warning": <true or false>,
  "notes": "<1-2 sentences>"
}}
"""
    return _parse_json(_call(prompt))


def generate_cover_letter(job: dict) -> str:
    prompt = f"""
You are an expert cover letter writer.
Write a concise, confident cover letter. No generic filler.
Output ONLY the cover letter text, no commentary.

CANDIDATE RESUME:
{BASE_RESUME}

JOB:
Title: {job.get('title', '')}
Company: {job.get('company', '')}
Description:
{job.get('description', '')}

Guidelines:
- 3 paragraphs, under 250 words total
- Para 1: Why this role and company specifically
- Para 2: 2-3 concrete achievements most relevant to this job
- Para 3: Short confident close
- Tone: Professional but human
"""
    return _call(prompt)


def generate_outreach_email(job: dict) -> dict:
    prompt = f"""
You are a job search coach. Write a short cold outreach email.
Respond ONLY with valid JSON, no markdown, no preamble.

Write a cold outreach email to the hiring manager at {job.get('company', 'this company')}
for the role of {job.get('title', 'this position')}.

CANDIDATE BACKGROUND:
{BASE_RESUME}

Guidelines:
- Subject line: specific, not clickbait
- Body: 4-5 sentences max, lead with value
- End with a low-friction ask (15-min call or resume review)

Return this exact JSON:
{{
  "subject": "<email subject>",
  "body": "<full email body>"
}}
"""
    return _parse_json(_call(prompt))
