"""
applicator/ats/__init__.py
Routes a full_form job URL to the correct ATS applicator class.
Returns None if the ATS is unrecognized (caller should queue for manual apply).
"""

import re

_ATS_PATTERNS = [
    (re.compile(r"greenhouse\.io|boards\.greenhouse\.io", re.I), "greenhouse"),
    (re.compile(r"lever\.co|jobs\.lever\.co",             re.I), "lever"),
    (re.compile(r"ashbyhq\.com|jobs\.ashbyhq\.com",       re.I), "ashby"),
    (re.compile(r"workday\.com|myworkdayjobs\.com",        re.I), "workday"),
]


def detect_ats(url: str) -> str | None:
    """Return ATS name for a URL, or None if unknown."""
    for pattern, name in _ATS_PATTERNS:
        if pattern.search(url or ""):
            return name
    return None


def route(url: str, headless: bool = True):
    """
    Return an instantiated applicator for the given ATS URL.
    Returns None if unrecognized.
    """
    ats = detect_ats(url)
    if ats == "greenhouse":
        from .greenhouse import GreenhouseApplicator
        return GreenhouseApplicator(headless=headless)
    if ats == "lever":
        from .lever import LeverApplicator
        return LeverApplicator(headless=headless)
    if ats == "ashby":
        from .ashby import AshbyApplicator
        return AshbyApplicator(headless=headless)
    # Workday is too dynamic — flag for manual review
    return None
