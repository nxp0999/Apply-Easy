"""
generate_html_pdf.py

Renders a plain-text resume into a pixel-perfect A4 PDF using
Playwright/Chromium — replaces pdflatex, zero system TeX dependency.

Input:  plain-text resume string (produced by pipeline/tex_parser.py)
Output: A4 PDF file at output_path
"""

import html as _html
import re
import os
import tempfile

# ── Section-marker pattern from tex_parser.py output ─────────────────────────
_DASH_LINE = re.compile(r"^[─\-]{4,}$")
_SEP = "  |  "   # subheading field separator injected by tex_parser


# ── CSS matching the LaTeX resume style ──────────────────────────────────────
_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
@page { size: A4; margin: 0.55in 0.62in 0.5in 0.62in; }

body {
    font-family: 'Calibri', 'Carlito', 'Arial', sans-serif;
    font-size: 10.5pt;
    color: #000;
    line-height: 1.25;
}

/* ─── Header ─────────────────────────────────────────────── */
.header { text-align: center; margin-bottom: 4pt; }
.name {
    font-size: 22pt;
    font-variant: small-caps;
    font-weight: bold;
    letter-spacing: 0.5pt;
}
.location { font-size: 9.5pt; margin-top: 2pt; }
.contact  { font-size: 9.5pt; margin-top: 1pt; }
.contact a { color: #000; text-decoration: underline; }

/* ─── Section ─────────────────────────────────────────────── */
.section { margin-top: 7pt; }
.section-title {
    font-size: 11.5pt;
    font-weight: bold;
    font-variant: small-caps;
    text-transform: uppercase;
    border-bottom: 1.5px solid #000;
    padding-bottom: 1pt;
    margin-bottom: 4pt;
}

/* ─── Sub-heading (company/project row) ──────────────────── */
.subheading       { margin-top: 3pt; }
.sh-row           { display: flex; justify-content: space-between; align-items: baseline; }
.sh-left          { font-weight: bold; font-size: 10.5pt; }
.sh-right         { font-size: 9.5pt;  font-weight: bold; white-space: nowrap; padding-left: 6pt; }
.sh-left2         { font-style: italic; font-size: 9.5pt; }
.sh-right2        { font-style: italic; font-size: 9.5pt; white-space: nowrap; padding-left: 6pt; }

/* ─── Bullets ─────────────────────────────────────────────── */
.bullets { list-style: disc; padding-left: 14pt; margin-top: 1pt; margin-bottom: 2pt; }
.bullets li { font-size: 9.5pt; line-height: 1.3; margin-bottom: 0.5pt; }

/* ─── Skills ──────────────────────────────────────────────── */
.skills-table { margin-top: 2pt; }
.skill-row    { font-size: 9.5pt; line-height: 1.4; }
.skill-cat    { font-weight: bold; }

/* ─── Certifications ──────────────────────────────────────── */
.cert-row { font-size: 9.5pt; line-height: 1.5; }
"""


def _e(s: str) -> str:
    return _html.escape(str(s))


# ── Resume parser ─────────────────────────────────────────────────────────────

def _parse(text: str) -> dict:
    """
    Parse tex_parser plain-text output into:
        { 'heading': [lines], 'sections': [{'name': str, 'lines': [str]}] }
    """
    lines = text.splitlines()
    heading: list[str] = []
    sections: list[dict] = []
    current: dict | None = None
    i = 0

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        if _DASH_LINE.match(stripped):
            # Next non-empty line is the section title, followed by another dash line
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                name = lines[j].strip().upper()
                k = j + 1
                if k < len(lines) and _DASH_LINE.match(lines[k].strip()):
                    k += 1
                current = {"name": name, "lines": []}
                sections.append(current)
                i = k
                continue
        elif current is None:
            if stripped:
                heading.append(stripped)
        else:
            current["lines"].append(raw)

        i += 1

    return {"heading": heading, "sections": sections}


# ── HTML renderers ─────────────────────────────────────────────────────────────

def _render_heading(heading_lines: list[str]) -> str:
    if not heading_lines:
        return ""

    name = heading_lines[0] if heading_lines else ""
    loc  = heading_lines[1] if len(heading_lines) > 1 else ""
    # Remaining lines are contact info — join with separator
    contact_parts = []
    for ln in heading_lines[2:]:
        for part in ln.split("  "):
            p = part.strip()
            if p:
                contact_parts.append(p)

    contact_html = " &nbsp;|&nbsp; ".join(_e(p) for p in contact_parts)

    return f"""
<div class="header">
  <div class="name">{_e(name)}</div>
  <div class="location">{_e(loc)}</div>
  <div class="contact">{contact_html}</div>
</div>"""


def _group_subheadings(lines: list[str]) -> list[dict]:
    """
    Group section lines into entries.
    Each entry = { 'sh': [row1, row2?], 'bullets': [...], 'plain': [...] }
    row format: "Left  |  Right"
    """
    entries: list[dict] = []
    current_entry: dict | None = None

    def _flush():
        if current_entry is not None:
            entries.append(current_entry)

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue

        is_bullet = stripped.startswith("•") or stripped.startswith("-")
        has_sep   = _SEP in raw and not is_bullet

        if has_sep:
            parts = raw.split(_SEP, 1)
            left  = parts[0].strip()
            right = parts[1].strip() if len(parts) > 1 else ""
            row   = (left, right)

            # First row of a new sub-heading block or second row of existing
            if current_entry and len(current_entry["sh"]) == 1 and not current_entry["bullets"]:
                # Second row of the same subheading
                current_entry["sh"].append(row)
            else:
                _flush()
                current_entry = {"sh": [row], "bullets": [], "plain": []}
        elif is_bullet:
            text = stripped.lstrip("•").lstrip("-").strip()
            if current_entry is None:
                current_entry = {"sh": [], "bullets": [], "plain": []}
            current_entry["bullets"].append(text)
        else:
            # Plain line (skills, certs, etc.)
            if current_entry is None:
                current_entry = {"sh": [], "bullets": [], "plain": []}
            current_entry["plain"].append(stripped)

    _flush()
    return entries


def _render_experience_section(lines: list[str]) -> str:
    entries = _group_subheadings(lines)
    parts = []
    for entry in entries:
        rows = entry["sh"]
        bullets = entry["bullets"]
        block = '<div class="subheading">'
        if rows:
            r1 = rows[0]
            block += f'<div class="sh-row"><span class="sh-left">{_e(r1[0])}</span><span class="sh-right">{_e(r1[1])}</span></div>'
        if len(rows) > 1:
            r2 = rows[1]
            block += f'<div class="sh-row"><span class="sh-left2">{_e(r2[0])}</span><span class="sh-right2">{_e(r2[1])}</span></div>'
        if bullets:
            items = "".join(f"<li>{_e(b)}</li>" for b in bullets)
            block += f'<ul class="bullets">{items}</ul>'
        block += "</div>"
        parts.append(block)
    return "\n".join(parts)


def _render_skills_section(lines: list[str]) -> str:
    parts = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        # Format: "Category: values"
        if ":" in stripped:
            cat, _, rest = stripped.partition(":")
            parts.append(
                f'<div class="skill-row"><span class="skill-cat">{_e(cat.strip())}:</span> {_e(rest.strip())}</div>'
            )
        else:
            parts.append(f'<div class="skill-row">{_e(stripped)}</div>')
    return f'<div class="skills-table">{"".join(parts)}</div>'


def _render_cert_section(lines: list[str]) -> str:
    parts = []
    for raw in lines:
        stripped = raw.strip()
        if stripped:
            parts.append(f'<div class="cert-row">{_e(stripped)}</div>')
    return "\n".join(parts)


def _render_section(section: dict) -> str:
    name  = section["name"]
    lines = section["lines"]

    if any(k in name for k in ("EXPERIENCE", "PROJECT")):
        body = _render_experience_section(lines)
    elif "SKILL" in name:
        body = _render_skills_section(lines)
    elif "CERTIF" in name:
        body = _render_cert_section(lines)
    elif "EDUCATION" in name:
        body = _render_experience_section(lines)
    else:
        body = _render_cert_section(lines)

    title = name.title()
    return f"""
<div class="section">
  <div class="section-title">{_e(title)}</div>
  {body}
</div>"""


# ── Public API ─────────────────────────────────────────────────────────────────

def build_html(resume_text: str) -> str:
    """Convert plain-text resume to a complete HTML document."""
    parsed = _parse(resume_text)

    heading_html   = _render_heading(parsed["heading"])
    sections_html  = "\n".join(_render_section(s) for s in parsed["sections"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Resume</title>
  <style>{_CSS}</style>
</head>
<body>
{heading_html}
{sections_html}
</body>
</html>"""


def generate_pdf(resume_text: str, output_path: str) -> str:
    """
    Render resume_text → A4 PDF at output_path using Playwright/Chromium.
    Returns output_path on success.
    """
    from playwright.sync_api import sync_playwright

    html_content = build_html(resume_text)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Write HTML to a temp file so Playwright can load it via file://
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w",
                                     encoding="utf-8", delete=False) as f:
        f.write(html_content)
        tmp_path = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()
            page.goto(f"file://{tmp_path}", wait_until="networkidle")
            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            browser.close()
    finally:
        os.unlink(tmp_path)

    return output_path


# ── CLI: generate PDF from my_resume.tex directly ────────────────────────────
if __name__ == "__main__":
    import sys
    from pipeline.tex_parser import load_tex_resume

    tex_path = sys.argv[1] if len(sys.argv) > 1 else "my_resume.tex"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "output/resume_preview.pdf"

    text = load_tex_resume(tex_path)
    generate_pdf(text, out_path)
    print(f"PDF written to {out_path}")
