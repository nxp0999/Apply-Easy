import os
import json
import re
import time
from groq import Groq
from config import BASE_RESUME
from resume_rules import (
    build_tailor_prompt, build_score_fit_prompt,
    build_score_tailored_prompt, build_cover_letter_prompt,
    build_outreach_prompt
)

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
    decoder = json.JSONDecoder()
    try:
        start = text.index("{")
        obj, _ = decoder.raw_decode(text[start:])
        return obj
    except Exception as e:
        raise ValueError(f"No JSON found: {text[:200]}")


def score_fit(job: dict) -> dict:
    return _parse_json(_call(build_score_fit_prompt(job, BASE_RESUME)))

def tailor_resume(job: dict) -> str:
    return _call(build_tailor_prompt(job, BASE_RESUME))

def score_tailored_resume(tailored: str) -> dict:
    return _parse_json(_call(build_score_tailored_prompt(tailored, BASE_RESUME)))

def generate_cover_letter(job: dict) -> str:
    return _call(build_cover_letter_prompt(job, BASE_RESUME))

def generate_outreach_email(job: dict) -> dict:
    return _parse_json(_call(build_outreach_prompt(job, BASE_RESUME)))
