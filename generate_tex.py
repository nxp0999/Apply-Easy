"""
generate_tex.py
Converts each resume_tailored.txt into a .tex file using your Overleaf template.

Usage:
    python3 generate_tex.py                    # process all jobs
    python3 generate_tex.py --job <job_id>     # process one specific job
    python3 generate_tex.py --compile          # also compile to PDF (needs pdflatex)
"""

import os
import re
import argparse
from config import OUTPUT_DIR


# ── LaTeX special character escaping ──────────────────────────────────────────

def escape(text: str) -> str:
    """Escape special LaTeX characters in plain text."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\textasciicircum{}"),
        ("<",  r"\textless{}"),
        (">",  r"\textgreater{}"),
    ]
    for char, rep in replacements:
        if char == "\\":
            text = text.replace(char, rep)
        else:
            text = text.replace(char, rep)
    return text


# ── Text parser — splits plain text resume into sections ──────────────────────

SECTION_HEADERS = [
    "SUMMARY", "EDUCATION", "CERTIFICATIONS", "PROFESSIONAL CERTIFICATIONS",
    "TECHNICAL SKILLS", "SKILLS", "EXPERIENCE", "PROFESSIONAL EXPERIENCE",
    "PROJECTS", "DATA SCIENCE PROJECT EXPERIENCE", "PROJECT EXPERIENCE"
]

def parse_sections(text: str) -> dict:
    """Split resume text into named sections."""
    sections = {}
    current = "HEADER"
    buf = []

    for line in text.splitlines():
        stripped = line.strip()
        is_header = any(
            stripped.upper() == h or stripped.upper().startswith(h + " ")
            for h in SECTION_HEADERS
        )
        if is_header and len(stripped) < 60:
            sections[current] = "\n".join(buf).strip()
            current = stripped.upper()
            buf = []
        else:
            buf.append(line)

    sections[current] = "\n".join(buf).strip()
    return sections


def get_section(sections: dict, *keys) -> str:
    """Try multiple possible section names, return first match."""
    for key in keys:
        for k, v in sections.items():
            if key in k.upper():
                return v
    return ""


# ── Section renderers ──────────────────────────────────────────────────────────

def render_summary(text: str) -> str:
    if not text.strip():
        return ""
    # Collapse the summary into one paragraph (2-3 lines from the AI)
    lines = " ".join(l.strip() for l in text.splitlines() if l.strip())
    return "\n".join([
        r"\section{Summary}",
        r"\vspace{2pt}",
        r" \begin{itemize}[leftmargin=0.15in, label={}]",
        r"    \small{\item{",
        f"     {escape(lines)}",
        r"    }}",
        r" \end{itemize}",
        r" \vspace{-12pt}",
    ])


def render_education(text: str) -> str:
    if not text.strip():
        return ""
    lines = [l for l in text.splitlines() if l.strip()]
    out = [r"\section{Education}", r"  \vspace{2pt}", r"  \resumeSubHeadingListStart"]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Detect institution line: contains "University" or "College" or "Institute"
        if any(w in line for w in ["University", "College", "Institute", "School"]):
            # Try to parse: "Institution — Date" or "Institution | Date"
            parts = re.split(r"\s*[—\|]\s*", line, maxsplit=1)
            institution = escape(parts[0].strip()) if parts else escape(line)
            date = escape(parts[1].strip()) if len(parts) > 1 else ""
            # Next line should be degree
            degree_line = lines[i+1].strip() if i+1 < len(lines) else ""
            degree_parts = re.split(r"\s*[—\|]\s*", degree_line, maxsplit=1)
            degree = escape(degree_parts[0].strip()) if degree_parts else escape(degree_line)
            location = escape(degree_parts[1].strip()) if len(degree_parts) > 1 else ""
            out.append(f"    \\resumeSubheading")
            out.append(f"      {{{institution}}}{{{date}}}")
            out.append(f"      {{{degree}}}{{{location}}}")
            out.append(r"      \resumeItemListStart")
            i += 2
            while i < len(lines):
                item = lines[i].strip()
                if not item:
                    i += 1
                    break
                if any(w in item for w in ["University", "College", "Institute", "School"]):
                    break
                # bullet lines
                item = re.sub(r"^[\-\•\*]\s*", "", item)
                if item:
                    out.append(f"        \\resumeItem{{{escape(item)}}}")
                i += 1
            out.append(r"      \resumeItemListEnd")
        else:
            i += 1
    out.append(r"  \resumeSubHeadingListEnd")
    return "\n".join(out)


def render_certifications(text: str) -> str:
    if not text.strip():
        return ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = [
        r"\section{Professional Certifications}",
        r"\vspace{2pt}",
        r" \begin{itemize}[leftmargin=0.15in, label={}]",
        r"    \small{\item{",
    ]
    for line in lines:
        line = re.sub(r"^[\-\•\*]\s*", "", line)
        if line:
            out.append(f"     \\textbf{{{escape(line)}}} \\\\")
    out += [r"    }}", r" \end{itemize}", r" \vspace{-15pt}"]
    return "\n".join(out)


def render_skills(text: str) -> str:
    if not text.strip():
        return ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = [
        r"\section{Technical Skills}",
        r"\vspace{2pt}",
        r" \begin{itemize}[leftmargin=0.15in, label={}]",
        r"    \small{\item{",
    ]
    for line in lines:
        # Try to detect "Category: items" format
        if ":" in line:
            colon_idx = line.index(":")
            category = line[:colon_idx].strip()
            items = line[colon_idx+1:].strip()
            out.append(f"     \\textbf{{{escape(category)}}}{{: {escape(items)}}} \\\\")
        else:
            out.append(f"     {escape(line)} \\\\")
    out += [r"    }}", r" \end{itemize}", r" \vspace{-15pt}"]
    return "\n".join(out)


def render_projects(text: str) -> str:
    if not text.strip():
        return ""
    lines = [l for l in text.splitlines() if l.strip()]
    out = [
        r"\section{Data Science Project Experience}",
        r"    \vspace{-2pt}",
        r"    \resumeSubHeadingListStart",
    ]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Project heading: not a bullet, contains | or has tech stack pattern
        if not line.startswith("-") and not line.startswith("•") and (
            "|" in line or re.search(r"\d{4}", line)
        ):
            # Split "Project Name | Tech | Date" or "Project Name | Tech"
            parts = re.split(r"\s*\|\s*", line)
            if len(parts) >= 3:
                name = parts[0].strip()
                tech = " | ".join(parts[1:-1]).strip()
                date = parts[-1].strip()
            elif len(parts) == 2:
                # Could be name | date or name | tech
                name = parts[0].strip()
                tech = ""
                date = parts[1].strip()
            else:
                name = line
                tech = ""
                date = ""

            # Format heading
            if tech:
                heading = f"\\textbf{{{escape(name)}}} $|$ \\emph{{{escape(tech)}}}"
            else:
                heading = f"\\textbf{{{escape(name)}}}"

            out.append(f"      \\resumeProjectHeading")
            out.append(f"          {{{heading}}}{{{escape(date)}}}")
            out.append(r"          \resumeItemListStart")
            i += 1
            while i < len(lines):
                item = lines[i].strip()
                if not item:
                    i += 1
                    break
                # Stop at next project heading
                if not item.startswith("-") and not item.startswith("•") and (
                    "|" in item or re.search(r"\d{4}", item)
                ) and len(item) < 120:
                    break
                item = re.sub(r"^[\-\•\*]\s*", "", item)
                if item:
                    out.append(f"            \\resumeItem{{{escape(item)}}}")
                i += 1
            out.append(r"          \resumeItemListEnd")
            out.append(r"          \vspace{-5pt}")
        else:
            i += 1
    out.append(r"    \resumeSubHeadingListEnd")
    out.append(r"\vspace{-2pt}")
    return "\n".join(out)


def render_experience(text: str) -> str:
    if not text.strip():
        return ""
    lines = [l for l in text.splitlines() if l.strip()]
    out = [
        r"\section{Professional Experience}",
        r"\vspace{2pt}",
        r"  \resumeSubHeadingListStart",
    ]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Company line: not a bullet, has date range pattern
        is_company = (
            not line.startswith("-") and not line.startswith("•")
            and re.search(r"\d{4}", line)
            and len(line) < 100
        )
        if is_company:
            # Parse "Company — Location | Date" or "Company | Date"
            date_match = re.search(r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}).+)", line)
            date = escape(date_match.group(1).strip()) if date_match else ""
            company_part = line[:date_match.start()].strip() if date_match else line
            company_part = re.sub(r"[\|—\-]+$", "", company_part).strip()
            company = escape(company_part)

            # Next line = title | tech or just title
            title_line = lines[i+1].strip() if i+1 < len(lines) else ""
            title_parts = re.split(r"\s*\|\s*", title_line, maxsplit=1)
            title = escape(title_parts[0].strip())
            tech  = escape(title_parts[1].strip()) if len(title_parts) > 1 else ""
            location = ""

            if tech:
                role = f"{{{title}}} $|$ \\emph{{{tech}}}"
            else:
                role = f"{{{title}}}"

            out.append(f"    \\resumeSubheading")
            out.append(f"      {{{company}}}{{{date}}}")
            out.append(f"      {{{role}}}{{{location}}}")
            out.append(r"      \resumeItemListStart")
            i += 2
            while i < len(lines):
                item = lines[i].strip()
                if not item:
                    i += 1
                    break
                if not item.startswith("-") and not item.startswith("•") and re.search(r"\d{4}", item):
                    break
                item = re.sub(r"^[\-\•\*]\s*", "", item)
                if item:
                    out.append(f"        \\resumeItem{{{escape(item)}}}")
                i += 1
            out.append(r"      \resumeItemListEnd")
            out.append(r"      \vspace{4pt}")
        else:
            i += 1
    out.append(r"  \resumeSubHeadingListEnd")
    out.append(r"\vspace{-6pt}")
    return "\n".join(out)


# ── Full document builder ──────────────────────────────────────────────────────

PREAMBLE = r"""\documentclass[a4paper,10.5pt]{article}

\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage{multicol}
\setlength{\multicolsep}{-3.0pt}
\setlength{\columnsep}{-1pt}
\input{glyphtounicode}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.6in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1.2in}
\addtolength{\topmargin}{-0.7in}
\addtolength{\textheight}{1.6in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-6pt}\scshape\raggedright\large\bfseries
}{}{0em}{}[\color{black}\titlerule \vspace{-6pt}]

\pdfgentounicode=1

\newcommand{\resumeItem}[1]{\item\small{{#1 \vspace{-3pt}}}}
\newcommand{\classesList}[4]{\item\small{{#1 #2 #3 #4 \vspace{-4pt}}}}
\newcommand{\resumeSubheading}[4]{
  \vspace{-3pt}\item
    \begin{tabular*}{1.0\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & \textbf{\small #2} \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-8pt}
}
\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-8pt}
}
\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{1.001\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & \textbf{\small #2}\\
    \end{tabular*}\vspace{-8pt}
}
\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-6pt}}
\renewcommand\labelitemi{$\vcenter{\hbox{\tiny$\bullet$}}$}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.0in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-6pt}}

\begin{document}"""

HEADING = r"""\begin{center}
    {\Huge \scshape Navaneeta Padmakumar} \\ \vspace{1pt}
    Richardson, Texas \\ \vspace{3pt}
    \small +1 945-338-9465 $|$ \href{mailto:nxp230016@utdallas.edu}{\underline{nxp230016@utdallas.edu}} $|$
    \href{https://linkedin.com/in/navaneetapk}{\underline{linkedin.com/in/navaneetapk}} $|$
    \href{https://github.com/nxp0999}{\underline{github.com/nxp0999}}
\end{center}
\vspace{-10pt}"""

END = r"\end{document}"


def build_tex(resume_text: str) -> str:
    sections = parse_sections(resume_text)

    # Render each section
    summ  = render_summary(get_section(sections, "SUMMARY"))
    skill = render_skills(get_section(sections, "SKILL"))
    exp   = render_experience(get_section(sections, "EXPERIENCE"))
    proj  = render_projects(get_section(sections, "PROJECT"))
    edu   = render_education(get_section(sections, "EDUCATION"))
    cert  = render_certifications(get_section(sections, "CERTIF"))

    # Order matches resume_rules.py SECTION_ORDER:
    # Name+Contact → Summary → Skills → Experience → Projects → Education → Certifications
    parts = [PREAMBLE, "", HEADING, ""]
    if summ:  parts += [summ, ""]
    if skill: parts += [skill, ""]
    if exp:   parts += [exp, ""]
    if proj:  parts += [proj, ""]
    if edu:   parts += [edu, ""]
    if cert:  parts += [cert, ""]
    parts.append(END)

    return "\n".join(parts)


# ── Main ──────────────────────────────────────────────────────────────────────

def process_job(job_dir: str, compile_pdf: bool = False):
    txt_path = os.path.join(job_dir, "resume_tailored.txt")
    tex_path = os.path.join(job_dir, "resume_tailored.tex")
    pdf_path = os.path.join(job_dir, "resume_tailored.pdf")

    if not os.path.exists(txt_path):
        return False

    with open(txt_path, "r") as f:
        text = f.read()
    text = re.sub(r"^(Here'?s?.*?:|Sure[,!].*?:|The (corrected|tailored|updated|revised).*?:)\s*\n","", text, flags=re.IGNORECASE).strip()

    tex = build_tex(text)

    with open(tex_path, "w") as f:
        f.write(tex)

    print(f"  ✓ {os.path.basename(job_dir)} → resume_tailored.tex")

    if compile_pdf:
        import subprocess

        # Compile twice (LaTeX needs 2 passes for accurate layout)
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode",
                 "-output-directory", job_dir, tex_path],
                capture_output=True, text=True
            )

        if os.path.exists(pdf_path):
            # Check page count
            page_count = _get_page_count(pdf_path)
            if page_count and page_count > 1:
                print(f"    ⚠ PDF is {page_count} pages — applying compression...")
                _compress_to_one_page(tex_path, job_dir)
            else:
                print(f"    ✓ PDF compiled ({page_count} page)")
        else:
            print(f"    ✗ PDF compile failed — check {tex_path}")

    return True


def _get_page_count(pdf_path: str) -> int:
    """Count pages in PDF using pdfinfo or pypdf."""
    try:
        import subprocess
        result = subprocess.run(
            ["pdfinfo", pdf_path],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if "Pages:" in line:
                return int(line.split(":")[1].strip())
    except Exception:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)
    except Exception:
        pass

    return None


def _compress_to_one_page(tex_path: str, job_dir: str):
    """Tighten spacing in .tex file to force one page, then recompile."""
    with open(tex_path, "r") as f:
        content = f.read()

    # Tighten spacing progressively
    replacements = [
        (r"\vspace{-10pt}", r"\vspace{-14pt}"),
        (r"\vspace{-15pt}", r"\vspace{-18pt}"),
        (r"\vspace{-6pt}",  r"\vspace{-8pt}"),
        (r"\vspace{-8pt}",  r"\vspace{-10pt}"),
        (r"\vspace{-3pt}",  r"\vspace{-5pt}"),
        (r"\vspace{2pt}",   r"\vspace{0pt}"),
        (r"\vspace{4pt}",   r"\vspace{2pt}"),
        (r"\vspace{-2pt}",  r"\vspace{-4pt}"),
        (r"\vspace{-5pt}",  r"\vspace{-7pt}"),
        (r"10.5pt",         r"10pt"),
        (r"\addtolength{\topmargin}{-0.7in}", r"\addtolength{\topmargin}{-0.85in}"),
        (r"\addtolength{\textheight}{1.6in}", r"\addtolength{\textheight}{1.9in}"),
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    with open(tex_path, "w") as f:
        f.write(content)

    # Recompile
    import subprocess
    for _ in range(2):
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode",
             "-output-directory", job_dir, tex_path],
            capture_output=True, text=True
        )

    pdf_path = os.path.join(job_dir, "resume_tailored.pdf")
    pages = _get_page_count(pdf_path)
    if pages == 1:
        print(f"    ✓ Compressed to 1 page successfully")
    else:
        print(f"    ⚠ Still {pages} pages — reduce content manually or lower font size further")


def main():
    parser = argparse.ArgumentParser(description="Generate .tex resumes from tailored text")
    parser.add_argument("--job",     help="Process a single job_id only")
    parser.add_argument("--compile", action="store_true", help="Also compile to PDF via pdflatex")
    args = parser.parse_args()

    if args.job:
        job_dir = os.path.join(OUTPUT_DIR, args.job)
        if not os.path.isdir(job_dir):
            print(f"Job folder not found: {job_dir}")
            return
        process_job(job_dir, args.compile)
        return

    # Process all jobs
    job_dirs = [
        os.path.join(OUTPUT_DIR, d)
        for d in os.listdir(OUTPUT_DIR)
        if os.path.isdir(os.path.join(OUTPUT_DIR, d))
    ]

    if not job_dirs:
        print("No job folders found in output/applications/")
        return

    print(f"Generating .tex files for {len(job_dirs)} jobs...\n")
    count = 0
    for job_dir in sorted(job_dirs):
        if process_job(job_dir, args.compile):
            count += 1

    print(f"\nDone. {count} .tex files generated.")
    print(f"Files saved alongside each resume_tailored.txt in output/applications/<job_id>/")

    if not args.compile:
        print("\nTo compile all to PDF, install pdflatex then run:")
        print("  python3 generate_tex.py --compile")
        print("\nOr upload any .tex file directly to Overleaf.")


if __name__ == "__main__":
    main()
