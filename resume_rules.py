"""
resume_rules.py
Single source of truth for all resume generation rules.
Used by both claude_tasks.py and ollama_tasks.py.
"""

SECTION_ORDER = """
MANDATORY SECTION ORDER:
1. Name + Contact Info
2. Summary (2-3 lines max)
3. Technical Skills
4. Professional Experience
5. Projects
6. Education
7. Professional Certifications
"""

ATS_RULES = """
ALL RULES ARE MANDATORY — NO EXCEPTIONS

ONE PAGE RULE:
- Output must fit on exactly ONE page at 10.5pt font
- Maximum 20 bullets total across the entire resume
- Maximum 3 bullets per role or project
- Summary must be 2-3 lines only
- Education: GPA only, no coursework, no extracurriculars

BULLET STRUCTURE — EVERY BULLET:
Action Verb + What you did (with specific tools and scale) + Result with number

GOOD: Built Spark pipeline processing 2M+ records, reducing runtime by 35%
BAD:  Worked on data pipeline using Spark

NUMBERS RULE:
- Every bullet must contain at least one specific number or percentage
- Use exact numbers from the original resume
- Never write a bullet without a measurable result

ACTION VERB RULES:
- Never use the same action verb more than ONCE across the entire resume
- Choose from this list — each verb can only be used one time total:

  Data & Analysis:
  Analyzed, Examined, Evaluated, Investigated, Assessed, Quantified,
  Modeled, Forecasted, Profiled, Segmented, Diagnosed, Benchmarked,
  Computed, Measured, Tracked, Monitored, Interpreted, Mapped

  Building & Engineering:
  Built, Developed, Engineered, Constructed, Architected, Designed,
  Implemented, Deployed, Configured, Integrated, Programmed, Coded,
  Assembled, Established, Launched, Prototyped, Authored, Formulated

  Improvement & Optimization:
  Optimized, Streamlined, Automated, Accelerated, Reduced, Improved,
  Enhanced, Upgraded, Refactored, Modernized, Simplified, Consolidated,
  Transformed, Overhauled, Restructured, Standardized, Calibrated, Tuned

  Leadership & Delivery:
  Led, Spearheaded, Directed, Coordinated, Facilitated, Managed,
  Executed, Delivered, Drove, Championed, Orchestrated, Pioneered,
  Steered, Initiated, Mobilized, Produced, Contributed, Collaborated

  Results & Achievement:
  Achieved, Generated, Increased, Boosted, Maximized, Accelerated,
  Secured, Captured, Enabled, Unlocked, Demonstrated, Validated,
  Verified, Confirmed, Proved, Surpassed, Exceeded, Attained

  Data Engineering & Pipelines:
  Migrated, Ingested, Processed, Transformed, Extracted, Loaded,
  Indexed, Partitioned, Queried, Serialized, Parallelized, Scheduled,
  Orchestrated, Versioned, Packaged, Published, Containerized, Provisioned

SYNONYM GUIDE — if you already used a verb, use its synonym instead:
  Built → Developed, Engineered, Constructed, Assembled
  Designed → Architected, Formulated, Structured, Drafted
  Analyzed → Examined, Evaluated, Investigated, Assessed
  Implemented → Deployed, Configured, Integrated, Established
  Optimized → Streamlined, Improved, Enhanced, Tuned
  Automated → Programmed, Scripted, Orchestrated, Scheduled
  Reduced → Minimized, Decreased, Cut, Trimmed
  Increased → Boosted, Maximized, Elevated, Grew
  Developed → Built, Engineered, Authored, Created
  Led → Spearheaded, Directed, Drove, Championed
  Generated → Produced, Delivered, Created, Yielded
  Monitored → Tracked, Observed, Measured, Surveyed
  Deployed → Launched, Released, Provisioned, Shipped
  Migrated → Transferred, Ported, Moved, Transitioned
- Never use: Worked on, Helped with, Responsible for, Assisted in,
  Participated in, Involved in, Tasked with, Demonstrating, Showcasing

KEYWORD RULES:
- Extract ALL required and preferred skills from the job description
- Place critical JD keywords in Summary AND Skills AND first bullet of latest role
- Use EXACT terminology from JD — write out full names, no abbreviations
- Aim to match 60-80% of JD keywords

SKILLS SECTION:
- Group in this order: Languages, Machine Learning, Big Data, Data Science,
  Data Engineering, Visualization, Tools and Platforms
- Include only skills relevant to this job
- Technical skills first always

DE-DUPLICATION:
- Every bullet must describe a completely different accomplishment
- No phrase or data point appears more than once in the entire resume
- Never write two bullets covering the same theme

DATE FORMAT:
- Consistent short format everywhere: Month YYYY (e.g. Mar 2021, Jan 2024)

PROJECT RULES:
- Include only 2-3 most relevant projects for this specific job
- Each project: exactly 2-3 bullets only
- Focus on: technologies used + scale + measurable results

NEVER:
- Fabricate experience, tools, metrics, or skills not in the original
- Change company names, job titles, dates, or GPA
- Remove any metric or number from the original
- Add filler phrases
- Include coursework in education
- Output anything except the resume text
"""


def build_tailor_prompt(job: dict, base_resume: str) -> str:
    return f"""You are an expert ATS resume writer in 2026.
Rewrite this resume to maximize its ATS score for the specific job below.
Follow every rule exactly.

{SECTION_ORDER}

{ATS_RULES}

TARGET JOB:
Title: {job.get('title', '')}
Company: {job.get('company', '')}

Job Description:
{job.get('description', '')[:2000]}

ORIGINAL RESUME — preserve all facts, numbers, and metrics exactly:
{base_resume}

Output ONLY the resume text. Nothing else."""


def build_score_fit_prompt(job: dict, base_resume: str) -> str:
    return f"""You are a strict technical recruiter. Rate this resume against the job.
Be realistic. Most candidates score 50-80. Only give 85+ for exceptional matches.
Respond with ONLY a JSON object.

RESUME:
{base_resume}

JOB TITLE: {job.get('title', '')}
COMPANY: {job.get('company', '')}
JOB DESCRIPTION:
{job.get('description', '')}

Return this exact JSON:
{{
  "score": <integer 0-100>,
  "verdict": "<one line summary>",
  "strengths": ["<strength1>", "<strength2>"],
  "gaps": ["<gap1>", "<gap2>"]
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
