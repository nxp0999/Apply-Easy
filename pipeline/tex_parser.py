"""
pipeline/tex_parser.py

Extracts clean plain text from the LaTeX resume file.
Produces higher-fidelity text than PDF extraction (no garbled chars,
no layout artifacts) and is used as BASE_RESUME throughout the pipeline.
"""

import re


def _extract_arg(s: str, pos: int) -> tuple[str, int]:
    """Extract one brace-delimited {…} argument starting at pos (must be '{')."""
    assert s[pos] == "{", f"Expected '{{' at pos {pos}, got {s[pos]!r}"
    depth = 0
    start = pos + 1
    i = pos
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start:i], i + 1
        i += 1
    return s[start:], len(s)


def _extract_n_args(s: str, n: int, start: int = 0) -> tuple[list[str], int]:
    """Extract exactly n brace-delimited arguments from s beginning at start."""
    args: list[str] = []
    pos = start
    while len(args) < n:
        while pos < len(s) and s[pos] in " \t\n":
            pos += 1
        if pos >= len(s) or s[pos] != "{":
            break
        arg, pos = _extract_arg(s, pos)
        args.append(arg)
    return args, pos


def _clean_inline(s: str) -> str:
    """Strip inline LaTeX commands from a string, leaving only text."""
    # \href{url}{text} → text
    s = re.sub(r"\\href\{[^}]+\}\{([^}]+)\}", r"\1", s)
    # \textXX{…}, \emph{…}, \underline{…}, \small{…}, \texttt{…}
    for cmd in ("textbf", "textit", "emph", "underline", "small",
                "texttt", "scshape", "Large", "Huge", "large",
                "normalsize", "footnotesize"):
        s = re.sub(rf"\\{cmd}\{{([^}}]*)\}}", r"\1", s)
    # $|$ → |,  $\vcenter{…}$ → ''
    s = re.sub(r"\$[^$]*\$", "", s)
    # \quad → ' ', \LaTeX → 'LaTeX', -- → –
    s = s.replace(r"\quad", "  ").replace(r"\LaTeX", "LaTeX").replace("--", "–")
    # remaining \cmd → ''
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    # stray braces
    s = s.replace("{", "").replace("}", "")
    # normalise whitespace
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def tex_to_text(tex: str) -> str:
    """Convert a LaTeX resume to clean plain text."""

    # ── 1. Isolate \begin{document} … \end{document} ──────────────────────
    m = re.search(r"\\begin\{document\}", tex)
    if m:
        tex = tex[m.end():]
    tex = re.sub(r"\\end\{document\}", "", tex)

    # ── 2. Strip comments ─────────────────────────────────────────────────
    tex = re.sub(r"(?m)%[^\n]*", "", tex)

    # ── 3. Handle \section{Name} ──────────────────────────────────────────
    def _process_section(m):
        name = _clean_inline(m.group(1))
        return f"\n\n{'─'*len(name)}\n{name.upper()}\n{'─'*len(name)}\n"

    tex = re.sub(r"\\section\{([^}]+)\}", _process_section, tex)

    # ── 4. Handle \resumeSubheading{A}{B}{C}{D} ───────────────────────────
    def _sub_heading(m):
        args, _ = _extract_n_args(m.string, 4, m.end())
        if len(args) == 4:
            co  = _clean_inline(args[0])
            dt  = _clean_inline(args[1])
            ttl = _clean_inline(args[2])
            loc = _clean_inline(args[3])
            return f"\n{co}  |  {dt}\n{ttl}  |  {loc}\n"
        return m.group(0)

    # Process \resumeSubheading with the brace-aware extractor
    result = []
    i = 0
    pattern = re.compile(r"\\resumeSubheading")
    for m in pattern.finditer(tex):
        result.append(tex[i:m.start()])
        args, end = _extract_n_args(tex, 4, m.end())
        if len(args) == 4:
            co  = _clean_inline(args[0])
            dt  = _clean_inline(args[1])
            ttl = _clean_inline(args[2])
            loc = _clean_inline(args[3])
            result.append(f"\n{co}  |  {dt}\n{ttl}  |  {loc}\n")
            i = end
        else:
            result.append(m.group(0))
            i = m.end()
    result.append(tex[i:])
    tex = "".join(result)

    # ── 5. Handle \resumeItem{content} ────────────────────────────────────
    result = []
    i = 0
    pattern = re.compile(r"\\resumeItem")
    for m in pattern.finditer(tex):
        result.append(tex[i:m.start()])
        while m.end() < len(tex) and tex[m.end()] in " \t\n":
            pass
        pos = m.end()
        while pos < len(tex) and tex[pos] in " \t\n":
            pos += 1
        if pos < len(tex) and tex[pos] == "{":
            content, end = _extract_arg(tex, pos)
            result.append(f"  • {_clean_inline(content)}\n")
            i = end
        else:
            result.append("  •\n")
            i = m.end()
    result.append(tex[i:])
    tex = "".join(result)

    # ── 6. Handle \textbf{Label:} value \\ patterns in skills ─────────────
    tex = re.sub(
        r"\\textbf\{([^}]+)\}([^\\]+)(?:\\\\|\n)",
        lambda m: f"  {_clean_inline(m.group(1))} {_clean_inline(m.group(2))}\n",
        tex,
    )

    # ── 7. Remove remaining LaTeX structural commands ─────────────────────
    for cmd in (
        "resumeSubHeadingListStart", "resumeSubHeadingListEnd",
        "resumeItemListStart", "resumeItemListEnd",
        "resumeProjectHeading",
        r"vspace\{[^}]*\}", r"hspace\{[^}]*\}",
        r"begin\{[^}]+\}", r"end\{[^}]+\}",
        r"addtolength\{[^}]+\}\{[^}]+\}",
        r"setlength\{[^}]+\}\{[^}]+\}",
        r"renewcommand[^{]*\{[^}]+\}(?:\{[^}]+\})?",
        r"newcommand[^{]*\{[^}]+\}(?:\[[^\]]+\])*(?:\{[^}]+\})?",
        r"usepackage(?:\[[^\]]+\])?\{[^}]+\}",
        r"titleformat[^}]+\}(?:\{[^}]+\}){4}",
        r"pagestyle\{[^}]+\}", "fancyhf\{\}", "fancyfoot\{\}",
        r"pdfgentounicode=[01]",
        r"urlstyle\{[^}]+\}",
        r"raggedbottom", "raggedright",
    ):
        tex = re.sub(rf"\\{cmd}", "", tex)

    # ── 8. Final inline cleanup ────────────────────────────────────────────
    tex = re.sub(r"\\href\{[^}]+\}\{([^}]+)\}", r"\1", tex)
    for cmd in ("textbf", "textit", "emph", "underline", "small",
                "texttt", "scshape", "Huge", "Large", "large",
                "normalsize", "footnotesize", "tiny"):
        tex = re.sub(rf"\\{cmd}\{{([^}}]*)\}}", r"\1", tex)
    tex = re.sub(r"\$[^$]*\$", "", tex)
    tex = tex.replace(r"\quad", "  ").replace(r"\LaTeX", "LaTeX")
    tex = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", "", tex)
    tex = tex.replace("{", "").replace("}", "")
    tex = tex.replace("\\\\", "\n").replace("\\", "")

    # ── 9. Normalise whitespace ───────────────────────────────────────────
    tex = re.sub(r"[ \t]+", " ", tex)
    tex = re.sub(r"\n{3,}", "\n\n", tex)
    return tex.strip()


def load_tex_resume(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    return tex_to_text(raw)
