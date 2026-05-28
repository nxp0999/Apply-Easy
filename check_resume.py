"""
check_resume.py
Checks a tailored resume against all ATS rules before submission.

Usage:
    python3 check_resume.py <path_to_resume.txt>
    python3 check_resume.py output/applications/<job_id>/resume_tailored.txt
"""

import sys
import re

from resume_rules import STRONG_VERBS

FILLER_PHRASES = [
    "responsible for","helped with","worked on","demonstrating expertise",
    "showcasing ability","passionate about","driven by","assisted with",
    "participated in","involved in","tasked with","duties included"
]

DATE_FORMATS = [
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b",
    r"\b\d{4}\b",
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b"
]

def extract_bullets(text):
    bullets = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("-") or line.startswith("•"):
            bullets.append(line.lstrip("-•* ").strip())
    return bullets

def check_resume(path):

    with open(path) as f:
        text = f.read()
    text = text.replace("**", "").replace("__", "")
    bullets = extract_bullets(text)
    issues = []
    passes = []

    # 1. Bullet count
    if len(bullets) <= 20:
        passes.append(f"✅ Bullet count: {len(bullets)} bullets (max 20)")
    else:
        issues.append(f"❌ Too many bullets: {len(bullets)} (max 20)")

    # 2. Quantified bullets
    quantified = [b for b in bullets if re.search(r"\d+", b)]
    pct = len(quantified) / len(bullets) * 100 if bullets else 0
    if pct >= 80:
        passes.append(f"✅ Quantified bullets: {len(quantified)}/{len(bullets)} ({pct:.0f}%)")
    else:
        issues.append(f"❌ Only {len(quantified)}/{len(bullets)} bullets quantified ({pct:.0f}%) — need 80%+")

    # 3. Filler phrases
    found_fillers = []
    for phrase in FILLER_PHRASES:
        if phrase.lower() in text.lower():
            found_fillers.append(phrase)
    if not found_fillers:
        passes.append("✅ No filler phrases found")
    else:
        issues.append(f"❌ Filler phrases found: {', '.join(found_fillers)}")

    # 4. Repeated action verbs
    verb_counts = {}
    for bullet in bullets:
        first_word = bullet.split()[0].lower().rstrip(".,") if bullet else ""
        if first_word in STRONG_VERBS:
            verb_counts[first_word] = verb_counts.get(first_word, 0) + 1
    overused = {v: c for v, c in verb_counts.items() if c > 1}
    if not overused:
        passes.append("✅ No repeated action verbs")
    else:
        issues.append(f"❌ Overused verbs: {overused}")

    # 5. Date consistency
    months_short = re.findall(r"\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", text)
    months_long  = re.findall(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b", text)
    if months_short and months_long:
        issues.append("❌ Inconsistent date format — mixing short and long month names")
    else:
        passes.append("✅ Date format consistent")

    # 6. Duplicate bullets
    seen = []
    dupes = []
    for b in bullets:
        words = set(b.lower().split())
        for s in seen:
            s_words = set(s.lower().split())
            overlap = len(words & s_words) / max(len(words), 1)
            if overlap > 0.75:
                dupes.append(b[:60])
                break
        seen.append(b)
    if not dupes:
        passes.append("✅ No duplicate or near-duplicate bullets")
    else:
        issues.append(f"❌ Similar bullets found:\n   " + "\n   ".join(dupes))

    # 7. Summary length
    summary_match = re.search(r"SUMMARY\n(.*?)(?:\n[A-Z]{3,}|\Z)", text, re.DOTALL)
    if summary_match:
        summary_lines = [l for l in summary_match.group(1).splitlines() if l.strip()]
        if len(summary_lines) <= 4:
            passes.append(f"✅ Summary length: {len(summary_lines)} lines")
        else:
            issues.append(f"❌ Summary too long: {len(summary_lines)} lines (max 4)")

    # 8. One page check (word count proxy)
    word_count = len(text.split())
    if word_count <= 650:
        passes.append(f"✅ Word count: {word_count} words (target: under 650)")
    else:
        issues.append(f"⚠️  Word count: {word_count} words (may exceed 1 page)")

    # ── Report ──────────────────────────────────────────────────────
    print("\n" + "="*55)
    print(" RESUME ATS CHECK REPORT")
    print("="*55)
    print(f" File: {path}")
    print(f" Bullets: {len(bullets)}  |  Words: {len(text.split())}")
    print("="*55)

    print("\n PASSED:")
    for p in passes:
        print(f"  {p}")

    if issues:
        print("\n ISSUES TO FIX:")
        for i in issues:
            print(f"  {i}")
    else:
        print("\n No issues found — resume is ready!")

    score = len(passes) / (len(passes) + len(issues)) * 100
    print(f"\n Overall check score: {score:.0f}% ({len(passes)}/{len(passes)+len(issues)} checks passed)")
    print("="*55 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Auto-find first available resume
        import os
        from config import OUTPUT_DIR
        dirs = [d for d in os.listdir(OUTPUT_DIR)
                if os.path.exists(os.path.join(OUTPUT_DIR, d, "resume_tailored.txt"))]
        if not dirs:
            print("No resumes found. Run --process first.")
            sys.exit(1)
        path = os.path.join(OUTPUT_DIR, dirs[0], "resume_tailored.txt")
        print(f"No file specified — checking: {path}")
    else:
        path = sys.argv[1]

    check_resume(path)
