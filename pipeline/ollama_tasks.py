import json
import re
import ollama
from config import BASE_RESUME
from resume_rules import (
    build_tailor_prompt, build_score_fit_prompt,
    build_score_tailored_prompt, build_cover_letter_prompt,
    build_outreach_prompt
)

MODEL = "mistral"


def _call(prompt: str) -> str:
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1},
    )
    return response["message"]["content"].strip()


def _parse_json(text: str) -> dict:
    text = re.sub(r"```json|```", "", text).strip()
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found: {text[:300]}")
    raw = text[start:end+1]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    raw = re.sub(r':\s*"(\d+)"', lambda m: f": {m.group(1)}", raw)
    raw = re.sub(r':\s*"true"',  ": true",  raw, flags=re.IGNORECASE)
    raw = re.sub(r':\s*"false"', ": false", raw, flags=re.IGNORECASE)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(raw)
        return obj


def score_fit(job: dict) -> dict:
    return _parse_json(_call(build_score_fit_prompt(job, BASE_RESUME)))

def tailor_resume(job: dict, missing_keywords: list = None) -> str:
    return _call(build_tailor_prompt(job, BASE_RESUME, missing_keywords=missing_keywords))

def score_tailored_resume(tailored: str) -> dict:
    return _parse_json(_call(build_score_tailored_prompt(tailored, BASE_RESUME)))

def generate_cover_letter(job: dict) -> str:
    return _call(build_cover_letter_prompt(job, BASE_RESUME))

def generate_outreach_email(job: dict) -> dict:
    return _parse_json(_call(build_outreach_prompt(job, BASE_RESUME)))
