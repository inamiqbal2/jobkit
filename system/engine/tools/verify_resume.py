#!/usr/bin/env python3
"""
Verify a tailored resume against the protocol in system/engine/charters/build.md.

Usage:
    <jobkit python> verify_resume.py Resume_<Name>_Company_Role.docx
    <jobkit python> verify_resume.py Resume_...docx --jd jd.txt
    <jobkit python> verify_resume.py Resume_...docx --terms "SEM,EBSD,failure analysis,Python"

Checks: page count, % vertical fill, parse test, keyword coverage, British spellings,
experience date order (2026-09-12), readability word caps (2026-09-12).
Requires: python-docx, pypdf, Pillow, LibreOffice (soffice), pdftoppm.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import argparse, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import get as _cfg, build as _build_cfg   # JOBKIT: identity + employer tokens + build.format from settings.yaml
_BUILD = _build_cfg()

# 2026-08-28: parse test made structure-aware. IDENTITY tokens must always parse; EMPLOYER tokens
# are checked only if that employer appears in the docx (entries now vary by JD — six exist).
MUST_PARSE = [x for x in (_cfg("identity.first_name", ""), _cfg("identity.phone", ""), _cfg("identity.email", "")) if x]   # JOBKIT: settings.yaml identity
EMPLOYER_TOKENS = list(_cfg("verification.employer_tokens", []) or [])   # JOBKIT: checked only when the resume mentions them

BRITISH = ["characterisation", "characterise", "modelling", "analyse", "optimis",
           "behaviour", "programme", "specialising", "finalis", "colour", "centre",
           "utilise", "organis", "recognis", "labour", "fibre"]

# Words too generic to treat as JD keywords
STOP = set("""a an the and or of for to in on with by as at from is are be will you your we our their
this that these those role job work experience years year ability able strong excellent good other
including include includes such using use used support supports team teams new all any per may can
must should required requirements preferred qualifications responsibilities skills etc into across
within more most than then them they it its who whom which what when where how while about over
under between during also both each other others than very much many few less least own same so
if but not no nor only just even still yet however therefore because since due via per""".split())


# ---- 2026-09-12 red-team defects 4 and 7 -----------------------------------------------------
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DATE_RE = re.compile(r"^(?:[A-Za-z]{3}[A-Za-z]*\.?\s+)?\d{4}\s*[-\u2013\u2014]\s*(?:(?:[A-Za-z]{3}[A-Za-z]*\.?\s+)?\d{4}|Present)\s*$", re.I)
SUMMARY_WARN, SUMMARY_FAIL = 45, 70
BULLET_WARN, BULLET_FAIL = 22, 30


def date_key(dates):
    """Same key as resume_builder.Resume._date_key: ("Present" first), start year, start month;
    year-only dates count as January."""
    m = re.match(r"\s*(?:([A-Za-z]{3})[A-Za-z]*\.?\s+)?(\d{4})", dates or "")
    if not m:
        return (0, 0, 0)
    month = _MONTHS.get((m.group(1) or "jan").lower(), 1)
    present = 1 if re.search(r"\bpresent\b", dates, re.I) else 0
    return (present, int(m.group(2)), month)


def experience_entries(paragraphs):
    """[(org, dates)] for the org/date lines between the EXPERIENCE heading and the next heading.
    The builder renders each entry header as 'Org<TAB>dates'."""
    out, inside = [], False
    for p in paragraphs:
        t = p.text.strip()
        if not t:
            continue
        if t.upper() == t and len(t.split()) <= 3 and p.style.name != "List Bullet":  # section heading
            inside = t.endswith("EXPERIENCE") or t.endswith("EXPEDITIONS")   # EXPERIENCE / RESEARCH EXPERIENCE / FIELD EXPERIENCE & EXPEDITIONS
            continue
        if inside and "\t" in p.text:
            org, dates = p.text.split("\t", 1)
            if _DATE_RE.match(dates.strip()):
                out.append((org.strip(), dates.strip()))
    return out


def readability(paragraphs):
    """(summary_words, [(words, text)] for every bullet)."""
    summary_words, bullets, grab = 0, [], False
    for p in paragraphs:
        t = p.text.strip()
        if not t:
            continue
        if t == "SUMMARY":
            grab = True; continue
        if grab:
            summary_words = len(t.split()); grab = False
        if p.style.name == "List Bullet":
            bullets.append((len(t.split()), t))
    return summary_words, bullets


def docx_text(path):
    from docx import Document
    d = Document(path)
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


def _soffice_candidates():
    """LibreOffice on PATH first, then the usual app locations (macOS .app, Windows Program Files, Linux)."""
    out = ["soffice", "--headless", "--convert-to", "pdf", "--outdir"], ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir"]
    extra = ["/Applications/LibreOffice.app/Contents/MacOS/soffice",
             os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
             r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
             "/usr/lib/libreoffice/program/soffice", "/snap/bin/libreoffice"]
    return list(out) + [[p, "--headless", "--convert-to", "pdf", "--outdir"] for p in extra if os.path.exists(p)]


def to_pdf(docx_path, outdir):
    for base in _soffice_candidates():
        cmd = base + [outdir, docx_path]
        try:
            subprocess.run(cmd, capture_output=True, timeout=180)
            pdf = os.path.join(outdir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
            if os.path.exists(pdf):
                return pdf
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def page_count(pdf):
    import pypdf
    return len(pypdf.PdfReader(pdf).pages)


def fill_pct(pdf, tmpdir):
    """Find where content ends on page 1, as % of page height."""
    from PIL import Image
    prefix = os.path.join(tmpdir, "pg")
    subprocess.run(["pdftoppm", "-jpeg", "-r", "100", "-f", "1", "-l", "1", pdf, prefix],
                   capture_output=True)
    imgs = [f for f in os.listdir(tmpdir) if f.startswith("pg") and f.endswith(".jpg")]
    if not imgs:
        return None
    im = Image.open(os.path.join(tmpdir, imgs[0])).convert("L")
    w, h = im.size
    px = im.load()
    last = 0
    for y in range(h):
        for x in range(0, w, 3):
            if px[x, y] < 160:
                last = y
                break
    return round(100 * last / h)


_FRAG = set("ll re ve d s t m".split())   # contraction tails: "you'll" -> "ll"


def jd_terms(jd_text, top=30):
    """ADVISORY keyword list (keywords.py with the lexicon is the real pass): multi-word phrases + acronyms from the
    posting, with HTML entities decoded and tags removed first, contractions kept whole and fragments dropped
    (audit v0.4 bug 17: "ll create", "ambitious goals.&nbsp" used to count as keywords)."""
    import html as _html
    clean = _html.unescape(re.sub(r"<[^>]+>", " ", jd_text or "")).replace("\xa0", " ")
    clean = re.sub(r"[\u2018\u2019]", "'", clean)
    text = clean.lower()
    cands = {}
    for m in re.finditer(r"(?<![a-z'])([a-z][a-z'\-/&]+(?: [a-z][a-z'\-/&]+){0,2})(?![a-z'])", text):
        ph = m.group(1).strip(" '-/&")
        words = ph.split()
        if len(words) < 2 or len(ph) < 8:
            continue
        if any(w in STOP or w in _FRAG or len(w) < 3 or "'" in w for w in words):
            continue
        cands[ph] = cands.get(ph, 0) + 1
    for m in re.finditer(r"\b([A-Z]{2,}(?:[/\-][A-Z]{2,})*)\b", clean):
        t = m.group(1).lower()
        if t not in STOP and len(t) >= 2:
            cands[t] = cands.get(t, 0) + 2
    return [t for t, _ in sorted(cands.items(), key=lambda kv: -kv[1])[:top]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--jd", help="path to job description text file")
    ap.add_argument("--terms", help="comma-separated keywords to check")
    ap.add_argument("--academic", action="store_true", help="CV mode: page range from settings.yaml build.cv_min_pages..cv_max_pages instead of the 1-page/fill checks (automatic when build.format is academic_cv or the file is CV*.docx)")
    a = ap.parse_args()
    if _BUILD["format"] == "academic_cv" or os.path.basename(a.docx).lower().startswith("cv"):
        a.academic = True

    text = docx_text(a.docx)
    low = text.lower()
    ok = True
    print(f"\n=== {os.path.basename(a.docx)} ===")

    with tempfile.TemporaryDirectory() as tmp:
        pdf = to_pdf(a.docx, tmp)
        if pdf:
            pages = page_count(pdf)
            if a.academic:
                lo, hi = _BUILD["cv_min_pages"], _BUILD["cv_max_pages"]
                good = lo <= pages <= hi
                ok &= good
                print(f"PAGES ................ {pages} {'PASS' if good else 'FAIL'} (CV mode: {lo}-{hi} pages per settings.yaml build.cv_min_pages/cv_max_pages)")
            else:
                good = pages == 1
                ok &= good
                print(f"PAGES ................ {pages} {'PASS' if good else 'FAIL (must be 1)'}")
                f = fill_pct(pdf, tmp)
                if pages != 1:
                    # 2026-10-01 audit: fill_pct measures PAGE 1 only, so on a 2-page render "94%" was meaningless
                    # (a forced 2-page docx reported FILL 95%). Report it as n/a instead of a number.
                    print(f"FILL ................. n/a (page-1 fill {f}% is not meaningful on {pages} pages; trim to 1 page first)")
                    f = None
                if f is not None:
                    # 90-93 as measured by LibreOffice: MS Word renders ~1 line looser, so
                    # >93% here risks spilling to page 2 in Word/Pages (observed 2026-08-24; ceiling 94->93 on 2026-10-01
                    # after two 94%-fill builds rendered as 2 pages).
                    good = 90 <= f <= 93
                    ok &= good
                    note = "PASS" if good else ("FAIL - underfilled, ADD REAL SUBSTANCE" if f < 90
                                               else "FAIL - Word spill risk, trim")
                    print(f"FILL ................. {f}% {note}")
        else:
            print("PAGES/FILL ........... SKIPPED (LibreOffice not available)")

    # docx text (pre-conversion truth) tells us which employer entries this resume actually uses
    try:
        from docx import Document as _D
        _dx = " ".join(p.text for p in _D(a.docx).paragraphs).lower()
    except Exception:
        _dx = low
    expected = MUST_PARSE + [e for e in EMPLOYER_TOKENS if e.lower() in _dx]
    missing = [m for m in expected if m.lower() not in low]
    ok &= not missing
    print(f"PARSE TEST ........... {len(expected)-len(missing)}/{len(expected)} "
          f"{'PASS' if not missing else 'FAIL missing: ' + str(missing)}")

    # DATE ORDER (defect 4): experience entries must be reverse-chronological
    try:
        from docx import Document as _D2
        _paras = list(_D2(a.docx).paragraphs)
    except Exception:
        _paras = []
    entries = experience_entries(_paras)
    keys = [date_key(d) for _, d in entries]
    in_order = keys == sorted(keys, reverse=True)
    ok &= in_order
    seq = " > ".join(d for _, d in entries) if entries else "no dated entries found"
    print(f"DATE ORDER ........... {'PASS' if in_order else 'FAIL not descending'}: {seq}")

    # READABILITY (defect 7): summary <= 45 words, bullets <= 22 words (WARN); FAIL at 70 / 30
    sw, bl = readability(_paras)
    long_b = [(n, t) for n, t in bl if n > BULLET_WARN]
    fail_b = [(n, t) for n, t in bl if n > BULLET_FAIL]
    if sw > SUMMARY_FAIL or fail_b:
        ok = False
        verdict = "FAIL"
    elif sw > SUMMARY_WARN or long_b:
        verdict = "WARN"
    else:
        verdict = "PASS"
    maxb = max([n for n, _ in bl], default=0)
    print(f"READABILITY .......... {verdict} summary {sw} words (warn>{SUMMARY_WARN}, fail>{SUMMARY_FAIL}); "
          f"{len(bl)} bullets, longest {maxb} words (warn>{BULLET_WARN}, fail>{BULLET_FAIL})")
    for n, t in long_b:
        print(f"  {'FAIL' if n > BULLET_FAIL else 'warn'} {n:>2}w: {t[:90]}{'...' if len(t) > 90 else ''}")
    # 2026-09-12 (original user): consecutive bullets opening with the same verb read as copy-paste
    # ("Root-caused ... / Root-caused ..."). WARN on any adjacent pair sharing a first word.
    _openers = [t.split()[0].lower().rstrip(',:;') for _, t in bl if t.split()]
    _dups = [(_openers[i], bl[i][1][:60]) for i in range(1, len(_openers)) if _openers[i] == _openers[i-1]]
    if _dups:
        print(f"OPENERS .............. WARN {len(_dups)} adjacent bullet(s) repeat an opener: " + "; ".join(f"'{w}' -> {t}..." for w, t in _dups[:3]))
    else:
        print("OPENERS .............. PASS no adjacent bullets share an opening word")

    import re as _re
    brit = sorted({b for b in BRITISH if (_re.search(r"analyse(?!s)", low) if b == "analyse" else b in low)})
    ok &= not brit
    print(f"AMERICAN ENGLISH ..... {'PASS' if not brit else 'FAIL British: ' + str(brit)}")

    terms = []
    if a.terms:
        terms = [t.strip() for t in a.terms.split(",") if t.strip()]
    elif a.jd:
        _jt = open(a.jd, encoding="utf-8", errors="ignore").read()
        terms = jd_terms(_jt.split("==========", 1)[1] if "==========" in _jt else _jt)   # v0.2: ignore the job-card header above the rule
    if terms:
        hit = [t for t in terms if t.lower() in low]
        miss = [t for t in terms if t.lower() not in low]
        pct = round(100 * len(hit) / len(terms))
        print(f"KEYWORD COVERAGE ..... {len(hit)}/{len(terms)} ({pct}%)  (advisory - the lexicon pass keywords.py decides)")
        if miss:
            print("  missing:", ", ".join(miss[:15]))
            print("  -> add ONLY terms the user genuinely has. Report the rest as honest gaps.")
    else:
        print("KEYWORD COVERAGE ..... skipped (pass --jd or --terms)")

    print(f"\nRESULT: {'PASS' if ok else 'NEEDS WORK'}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
