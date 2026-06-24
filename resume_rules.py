"""
resume_rules.py
Prompts for job-specific resume tailoring and ATS quality scoring.
Formatting is handled by generate_tex.py — this file only generates content.
"""


def build_tailor_prompt(job: dict, base_resume: str, missing_keywords: list = None) -> str:
    kw_note = ""
    if missing_keywords:
        kw_note = (
            f"\nKeywords to weave into existing bullets where they genuinely fit "
            f"(never fabricate): {', '.join(missing_keywords)}"
        )
    return f"""Make minimal, targeted edits to this resume to match the job below.

Rules:
- Keep EVERY section, bullet, project, metric, and achievement from the original exactly as written
- Do NOT add sections that are not in the original resume
- Inject 1-3 missing keywords into existing bullets where they fit naturally
- Do NOT add new bullets, delete anything, or change any numbers, dates, or company names
- Output the complete resume in the same format and with the same sections as the input{kw_note}

JOB: {job.get('title', '')} at {job.get('company', '')}
{job.get('description', '')[:1500]}

RESUME:
{base_resume}

Output ONLY the resume text."""



def build_score_fit_prompt(job: dict, base_resume: str) -> str:
    return f"""You are a strict ATS system scoring resume-job fit.
Score each dimension independently then compute the weighted total.
Respond with ONLY a JSON object — no explanation, no markdown.

RESUME:
{base_resume}

JOB TITLE: {job.get('title', '')}
COMPANY: {job.get('company', '')}
JOB DESCRIPTION:
{job.get('description', '')[:5000]}

Scoring weights:
  final_score = (keyword_overlap * 0.35) + (title_match * 0.20)
              + (experience_level * 0.15) + (tech_stack * 0.20)
              + (location_match * 0.10)

Be strict: most resumes score 45–75. Only give 80+ for strong matches.

Return this exact JSON:
{{
  "score": <final_score as integer>,
  "keyword_overlap": <0-100>,
  "title_match": <0-100>,
  "experience_level": <0-100>,
  "tech_stack": <0-100>,
  "location_match": <0-100>,
  "verdict": "<one line>",
  "strengths": ["<strength1>", "<strength2>"],
  "gaps": ["<gap1>", "<gap2>"],
  "missing_keywords": ["<kw1>", "<kw2>", "<kw3>"]
}}"""


def build_score_tailored_prompt(tailored: str, base_resume: str) -> str:
    return f"""You are a resume quality auditor.
Compare the TAILORED resume against the ORIGINAL. Respond with ONLY a JSON object.

ORIGINAL:
{base_resume[:1500]}

TAILORED:
{tailored[:1500]}

Return this exact JSON:
{{
  "overall": <integer 0-100>,
  "factual_accuracy": <integer 0-100>,
  "ats_score": <integer 0-100>,
  "clarity": <integer 0-100>,
  "drift_warning": <true or false>,
  "notes": "<one sentence>"
}}"""


def build_cover_letter_prompt(job: dict, base_resume: str) -> str:
    return f"""You are an expert cover letter writer.
Write a concise confident cover letter. No generic filler.
Output ONLY the cover letter text.

CANDIDATE RESUME:
{base_resume[:2000]}

JOB: {job.get('title', '')} at {job.get('company', '')}
DESCRIPTION: {job.get('description', '')[:800]}

Rules:
- 3 paragraphs, under 250 words total
- Para 1: Why this specific role and company
- Para 2: 2-3 concrete achievements with numbers most relevant to this job
- Para 3: Short confident close with call to action
- Professional but human tone
- Never use filler phrases"""


STRONG_VERBS = [
    "built","designed","implemented","automated","optimized","reduced",
    "increased","deployed","led","analyzed","developed","engineered",
    "achieved","constructed","architected","established","evaluated",
    "identified","executed","streamlined","delivered","spearheaded",
    "generated","maintained","validated","configured","investigated",
    "produced","transformed","leveraged","monitored","migrated",
    "orchestrated","accelerated","enhanced","standardized","consolidated",
    "integrated","launched","resolved","pioneered","restructured",
    "computed","modeled","forecasted","segmented","profiled","benchmarked",
    "partitioned","indexed","parallelized","scheduled","versioned",
    "containerized","provisioned","extracted","classified","clustered",
    "visualized","quantified","measured","tracked","processed",
]


def build_outreach_prompt(job: dict, base_resume: str) -> str:
    return f"""You are a job search coach. Write a cold outreach email.
Respond with ONLY a JSON object.

Job: {job.get('title', '')} at {job.get('company', '')}

CANDIDATE BACKGROUND:
{base_resume[:1000]}

Rules:
- Subject: specific, mentions role and one key skill
- Body: 4-5 sentences, lead with value not "I saw your posting"
- Mention one specific achievement with a number — use ONLY numbers from the candidate background above, never invent metrics
- End with low-friction ask (15-min call)
- NEVER fabricate metrics, company names, or achievements not in the candidate background

Return this exact JSON:
{{
  "subject": "<email subject>",
  "body": "<full email body>"
}}"""
