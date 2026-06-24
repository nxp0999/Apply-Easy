"""
applicator/base.py
Shared utilities and abstract base class for all platform applicators.
"""

import glob
import logging
import os
from abc import ABC, abstractmethod

from config import CREDENTIALS, OUTPUT_DIR, PROFILE

logger = logging.getLogger(__name__)


# ── File helpers ──────────────────────────────────────────────────────────────

def find_pdf(job_id: str) -> str | None:
    """
    Locate the tailored PDF for a job.
    Prefers the named copy (e.g. 'Data-Scientist-Navaneeta-Padmakumar-Google.pdf')
    and falls back to 'resume_tailored.pdf'.
    """
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    if not os.path.isdir(job_dir):
        return None
    named = sorted(glob.glob(os.path.join(job_dir, f"*-{PROFILE['first_name']}*-{PROFILE['last_name']}-*.pdf")))
    if named:
        return named[0]
    fallback = os.path.join(job_dir, "resume_tailored.pdf")
    return fallback if os.path.exists(fallback) else None


def get_cover_letter(job_id: str) -> str:
    """Read the generated cover letter text for a job."""
    path = os.path.join(OUTPUT_DIR, job_id, "cover_letter.txt")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return ""


# ── Abstract base ─────────────────────────────────────────────────────────────

class BaseApplicator(ABC):
    """
    All platform/ATS applicators inherit from this class.

    apply() must return:
        {"success": bool, "notes": str}
    """

    PLATFORM: str = ""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.profile = dict(PROFILE)  # per-instance copy so job-specific updates don't leak
        self.credentials = CREDENTIALS.get(self.PLATFORM, {})

    def _update_for_job(self, job: dict):
        """
        Refresh profile fields that depend on the specific job.
        Call this at the top of every subclass apply() before any form filling.
        """
        location = (job.get("location") or "").lower()
        # Needs visa sponsorship only if the job is NOT in India
        if not location or "india" in location:
            self.profile["visa_sponsorship"] = "No"
        else:
            self.profile["visa_sponsorship"] = "Yes"

    @abstractmethod
    def apply(self, job: dict, pdf_path: str, dry_run: bool = False) -> dict:
        ...

    # ── Playwright helpers shared across subclasses ───────────────────────────

    def _launch_browser(self, p):
        return p.chromium.launch(
            headless=self.headless,
            slow_mo=80 if not self.headless else 0,
            args=["--disable-blink-features=AutomationControlled"],
        )

    def _get_label_text(self, field, page) -> str:
        """Return the visible label text for an input element."""
        try:
            fid = field.get_attribute("id")
            if fid:
                lbl = page.locator(f'label[for="{fid}"]')
                if lbl.count():
                    return lbl.first.inner_text().strip().lower()
            placeholder = field.get_attribute("placeholder") or ""
            aria        = field.get_attribute("aria-label")  or ""
            name        = field.get_attribute("name")         or ""
            return f"{placeholder} {aria} {name}".strip().lower()
        except Exception:
            return ""

    def _infer_value(self, label: str) -> str | None:
        """
        Map a field label to a profile value.
        Returns None if no match → caller decides whether to skip or use a default.
        """
        p = self.profile
        checks = [
            (["first name", "firstname"],           p["first_name"]),
            (["last name", "lastname", "surname"],  p["last_name"]),
            (["full name", "your name"],            p["full_name"]),
            (["email"],                             p["email"]),
            (["phone", "mobile", "tel"],            p["phone"]),
            (["city"],                              p["city"]),
            (["state", "province"],                 p["state"]),
            (["country"],                           p["country"]),
            (["linkedin"],                          p["linkedin_url"]),
            (["github"],                            p["github_url"]),
            (["website", "portfolio"],              p["linkedin_url"]),
            (["current company", "employer", "organization", "org"],  p.get("current_company", "")),
            (["year", "experience", "years"],       p["years_experience"]),
            (["notice", "availability"],            p["notice_period"]),
            (["salary", "ctc", "compensation", "expected"],  p["salary_expected"]),
            (["sponsor", "visa"],                   p["visa_sponsorship"]),
            (["authoriz", "eligible", "work permit"], p["work_authorization"]),
            (["relocat"],                           p["willing_to_relocate"]),
            (["citizen", "us citizen", "green card"], p["us_citizen"]),
        ]
        for keywords, value in checks:
            if any(kw in label for kw in keywords):
                return value
        return None
