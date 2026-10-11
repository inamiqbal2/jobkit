#!/usr/bin/env python3
"""Honesty audit for built documents. Run on EVERY .docx before it is shown to the person (CONSTITUTION I.1, I.8).
All claim boundaries come from My Job Search/profile/approved_claims.yaml (via approved_claims.py).

WHITELIST (v0.5, audit bug 5): a resume or CV is a list of approved sentences, nothing else.
  Every non-structural paragraph of a resume (Resume*.docx / build.resume_filename) or CV (CV*.docx / build.cv_filename)
  must equal, whitespace-normalized and case-insensitive, a text the YAML approves: an experience / education / field /
  teaching tuple line ("org dates", "role loc"), a named bullet, a project title or bullet, a skills line, a cv.* item,
  a publications / tenure line, a constant, or a summary (optionally prefixed by the posting's role noun, at most 60
  characters, e.g. "ICU registered nurse candidate: <approved summary>"; optionally followed by the approved tenure line).
  Exempt BY STRUCTURE, never by content: the name line (equals identity.name), the contact line (the paragraph right
  after the name, or any paragraph carrying the email / phone), section headings (all-caps, <= 6 words, not a bullet),
  and the LABEL part of a "Label : text" skills line (the text part must still be approved).
  An invented bullet, a paraphrased bullet, a pending claim, a number nobody confirmed: all fail here.

BLACKLIST (kept): never_claims.forbidden_terms (word-bounded), never_claims.operator_patterns (clause-aware: hedged_phrases
  make an instrument mention acceptable), retired_claims regexes, pending[].claim (a paraphrase of an unconfirmed claim is
  caught by its numbers + words), experience[].frozen (bullets under that heading verbatim), banned_words, and the
  work-authorization line (settings.yaml work_authorization.resume_line must appear verbatim on a resume / CV).

LETTERS AND STATEMENTS (every other .docx in the folder): prose, so no line-by-line whitelist; instead the blacklist
  above PLUS a number check: every number in the letter (12, 40%, $4M, 500 L, 2019) must appear in an approved text, in
  a CONFIRMED evidence file (profile/evidence/*.md with Status: CONFIRMED-BY-USER), or - for sentences that are not about
  the person (no I / my / me) - in the folder's JobDescription.txt (facts quoted from the posting). A date line
  ("October 11, 2026") is exempt. Unsourced numbers are the commonest fabrication in a letter; this catches them.

AUDIT_PASS.json: when EVERY .docx in an application folder passes, the folder gets applications/<folder>/AUDIT_PASS.json
  (date, sha256 of every .docx). decide.py BUILT refuses unless that file exists and the hashes still match, so a
  document that was never audited, or was rebuilt after the audit, cannot be recorded as built.

Usage: <jobkit python> audit_claims.py <folder-or-docx> [...]   (exit 1 if any file fails)"""
import re, sys, glob, os, json, hashlib, datetime
from docx import Document
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import approved_claims as _ac
from userconfig import build as _build_cfg, get as _cfg, EVIDENCE as _EVIDENCE

PASS_FILE = "AUDIT_PASS.json"


def _is_cv(path):
    base = os.path.basename(path).lower()
    return base.startswith("cv") or base == os.path.basename(str(_build_cfg().get("cv_filename", ""))).lower()


def _is_resume(path):
    base = os.path.basename(path).lower()
    return base.startswith("resume") or base == os.path.basename(str(_build_cfg().get("resume_filename", ""))).lower() or _is_cv(path)


def _norm_dates(d):
    return re.sub(r"\bSept\b\.?", "Sep", str(d or ""))


def _approved_set():
    """Every normalized string a resume / CV line may equal (the builder's composed lines included)."""
    ok = _ac.approved_texts()
    n = _ac._norm
    for e in _ac.EXPERIENCE + _ac.CV_FIELD + [t for t in _ac.CV_TEACHING if isinstance(t, dict)]:
        org = e.get("org") or e.get("title") or ""
        for d in (e.get("dates", ""), _norm_dates(e.get("dates", ""))):
            ok.add(n(f"{org} {d}"))
        ok.add(n(f"{e.get('role') or e.get('title') or ''} {e.get('loc', '')}"))
    for v in _ac.ENTRY_VARIANTS.values():
        for d in (v[1], _norm_dates(v[1])):
            ok.add(n(f"{v[0]} {d}"))
        ok.add(n(f"{v[2]} {v[3]}"))
    for e in _ac.CV_EDUCATION:
        ok.add(n(f"{e.get('institution', '')} {e.get('dates', '')}")); ok.add(n(f"{e.get('degree', '')} {e.get('loc', '')}"))
        ok.add(n(e.get("degree", "")))
    for e in (_cfg("education", []) or []):
        ok.add(n(f"{e.get('institution', '')} {e.get('dates', '')}")); ok.add(n(e.get("line", "")))
    for lab, (l, t) in {**_ac.SKILLS_LINES, **_ac.CV_SKILLS}.items():
        ok.add(n(f"{l} : {t}")); ok.add(n(f"{l}: {t}"))
    for c in _ac.CONSTANTS.values():
        if isinstance(c, tuple) and len(c) == 2:
            ok.add(n(f"{c[0]} : {c[1]}")); ok.add(n(f"{c[0]}: {c[1]}"))
    for p in (_ac.PUBS, _ac.PUBS_SHORT):
        if p:
            ok.add(n(f"{p[0]} : {p[1]}")); ok.add(n(f"{p[0]}: {p[1]}"))
    refs = _ac.CV_REFERENCES
    for t in (refs if isinstance(refs, list) else [refs]):
        ok.add(n(t))
    ok.discard("")
    return ok


def _traceability(paras):
    """Untraceable paragraphs of a resume / CV (see module docstring). Returns a list of offending texts."""
    ok = _approved_set()
    n = _ac._norm
    summaries = {n(v) for v in _ac.SUMMARIES.values() if v}
    tenures = {n(t) for t in (_ac.TENURE, _ac.TENURE_SHORT) if t}
    name = str(_cfg("identity.name", "") or "").strip()
    phone = str(_cfg("identity.phone", "") or "").strip(); email = str(_cfg("identity.email", "") or "").strip()
    nonempty = [q for q in paras if q.text.strip()]
    bad = []
    for i, q in enumerate(nonempty):
        t = q.text.strip()
        is_list = q.style.name.startswith("List")
        if name and t == name:
            continue                                            # name line (structure)
        if (i == 1 and name and nonempty[0].text.strip() == name) or (email and email in t) or (phone and phone in t):
            continue                                            # contact line (structure)
        if t.upper() == t and len(t.split()) <= 6 and not is_list:
            continue                                            # section heading (structure)
        tn = n(re.sub(r"^\d+\.\s*", "", t))                      # numbered publication
        if tn in ok:
            continue
        # "Label : approved text" - the label is structure, the text must be approved
        m = re.match(r"^([^:]{1,40}?)\s*:\s*(.+)$", t)
        if m and len(m.group(1).split()) <= 5 and n(m.group(2)) in ok:
            continue
        # "<role noun prefix (<= 60 chars)>: <approved summary>[ <approved tenure line>]"
        body = tn.rstrip(" .;,")
        for tl in tenures:
            tl = tl.rstrip(" .;,")
            if body.endswith(" " + tl):
                body = body[: -len(tl) - 1].rstrip(" .;,")
        if any(body.endswith(sm.rstrip(" .;,")) and len(body) - len(sm.rstrip(" .;,")) <= 60 for sm in summaries):
            continue
        bad.append(t[:80])
    return bad


# ---- letters / statements: numbers must be sourced -----------------------------------------------------------------
_NUM = re.compile(r"(?<![A-Za-z])(?:\$\s?\d[\d,]*(?:\.\d+)?\s?[kKmM]?|\d[\d,]*(?:\.\d+)?\s?%|\d[\d,]*(?:\.\d+)?)(?![A-Za-z\d])")
_DATE_LINE = re.compile(r"^\s*(?:[A-Z][a-z]+\.? \d{1,2}, \d{4}|\d{1,2} [A-Z][a-z]+ \d{4}|\d{4}-\d\d-\d\d)\s*$")
_FIRST_PERSON = re.compile(r"\b(I|I'm|I've|I'd|my|me|mine|myself)\b")


def _numtok(s):
    return re.sub(r"[\s,]", "", s).lower()


def _confirmed_evidence_text():
    out = []
    for p in sorted(glob.glob(os.path.join(_EVIDENCE, "*.md"))):
        try:
            t = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if re.search(r"^Status:\s*CONFIRMED-BY-USER", t, re.M | re.I):
            out.append(t)
    return "\n".join(out)


def _jd_text(path):
    d = os.path.dirname(os.path.abspath(path))
    for name in ("JobDescription.txt", "JobDescription_FULL.txt", "JD.txt"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            try:
                return open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                pass
    return ""


def _letter_numbers(paras, path):
    """Numbers in a letter / statement that no approved text, confirmed evidence file or (for third-person sentences)
    the posting itself carries. Returns ["<number> in: <sentence>"...]."""
    pool_person = " ".join(sorted(_ac.approved_texts())) + "\n" + _confirmed_evidence_text().lower()
    pool_person += " " + " ".join(str(e.get(k, "")) for e in (_cfg("education", []) or []) for k in ("dates", "line")).lower()
    pool_person += " " + str(_cfg("identity.phone", "")) + " " + " ".join(str(x) for x in (_cfg("identity.links", []) or []))
    pool_job = _jd_text(path).lower()
    toks_person = {_numtok(m.group(0)) for m in _NUM.finditer(pool_person)}
    toks_job = {_numtok(m.group(0)) for m in _NUM.finditer(pool_job)}
    bad = []
    for q in paras:
        t = q.text.strip()
        if not t or _DATE_LINE.match(t):
            continue
        for sent in re.split(r"(?<=[.;!?])\s+", t):
            first = bool(_FIRST_PERSON.search(sent))
            for m in _NUM.finditer(sent):
                tok = _numtok(m.group(0))
                if tok in toks_person or (not first and tok in toks_job):
                    continue
                bad.append(f"{m.group(0).strip()} in: {sent[:70]}")
    return bad


def _pending_hits(t):
    """A paraphrase of a PENDING claim: its numbers plus one of its significant words within 80 characters."""
    hits = []
    low = t.lower()
    for p in _ac.PENDING:
        claim = str((p.get("claim") if isinstance(p, dict) else p) or "")
        nums = [_numtok(m.group(0)) for m in _NUM.finditer(claim)]
        words = [w for w in re.findall(r"[a-z]{5,}", claim.lower())]
        if not nums or not words:
            continue
        for m in _NUM.finditer(low):
            if _numtok(m.group(0)) in nums:
                win = low[max(0, m.start() - 80): m.end() + 80]
                if any(w in win for w in words):
                    hits.append(claim[:60]); break
    return hits


def check(path):
    problems = []
    if not _ac.loaded():
        return ["profile/approved_claims.yaml is missing - nothing can be audited (run onboarding first)"]
    doc = Document(path)
    paras = [q for q in doc.paragraphs]
    t = " ".join(p.text for p in paras)
    is_resume = _is_resume(path)

    hits = [w for w in _ac.FORBIDDEN if re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", t, re.I)]
    if hits:
        problems.append(f"forbidden terms: {hits}")

    pats = []
    for p in _ac.OPERATOR_PATTERNS:
        for m in re.finditer(p, t, re.I):
            clause = t[max(0, m.start() - 80): m.end() + 80]
            if any(h.lower() in clause.lower() for h in _ac.HEDGED_PHRASES):
                continue
            pats.append(m.group(0))
    if pats:
        problems.append(f"operator-implying: {pats}")

    ret = [m.group(0) for p in _ac.RETIRED for m in re.finditer(p, t, re.I)]
    if ret:
        problems.append(f"RETIRED claims: {ret}")
    pend = _pending_hits(t)
    if pend:
        problems.append(f"PENDING (unconfirmed) claims used: {pend}")

    # frozen entries: every bullet under the employer heading must be an approved bullet verbatim
    nonempty = [q for q in paras if q.text.strip()]
    for org, approved in _ac.FROZEN.items():
        if not org:
            continue
        for i, q in enumerate(nonempty):
            if q.text.startswith(org):
                j = i + 2   # skip the role/location line the builder writes under the org line
                while j < len(nonempty) and nonempty[j].style.name.startswith("List"):
                    b = nonempty[j].text.strip()
                    if not any(b == a.strip() for a in approved):
                        problems.append(f"{org}: bullet not from approved constants: {b[:70]}")
                    j += 1
                break
        else:
            if is_resume and org in t and not any(a in t for a in approved):
                problems.append(f"{org}: bullet not from approved constants")

    if is_resume and _ac.WORK_AUTH_LINE and _ac.WORK_AUTH_LINE not in t:
        problems.append("MISSING work-auth line")
    if is_resume:
        untraced = _traceability(paras)
        if untraced:
            problems.append(f"{'CV' if _is_cv(path) else 'resume'} traceability: {len(untraced)} line(s) not in approved_claims.yaml: {untraced[:3]}")
    else:
        unsourced = _letter_numbers(paras, path)
        if unsourced:
            problems.append(f"letter: {len(unsourced)} number(s) with no approved / confirmed source: {unsourced[:3]}")
    for w in _ac.BANNED_WORDS:
        if is_resume and re.search(rf"\b{re.escape(w)}\b", t, re.I):
            problems.append(f"contains the banned word '{w}'")
    return problems


# ---- AUDIT_PASS.json ---------------------------------------------------------------------------------------------------
def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def write_pass(folder, files):
    """Record that every .docx in `folder` passed (called by main after a clean folder run)."""
    rec = {"date": datetime.date.today().isoformat(), "audit": "audit_claims.py",
           "files": {os.path.basename(f): _sha(f) for f in files}}
    with open(os.path.join(folder, PASS_FILE), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1); f.write("\n")
    return rec


def pass_status(folder):
    """(ok, message) - is there a fresh AUDIT_PASS.json covering every .docx now in the folder?"""
    p = os.path.join(folder, PASS_FILE)
    docs = sorted(glob.glob(os.path.join(folder, "*.docx")))
    if not docs:
        return False, f"no .docx in {folder}"
    if not os.path.exists(p):
        return False, f"no {PASS_FILE} in {folder} - run audit_claims.py on the folder first"
    try:
        rec = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        return False, f"{PASS_FILE} unreadable ({e}) - run audit_claims.py on the folder again"
    have = rec.get("files") or {}
    for d in docs:
        b = os.path.basename(d)
        if b not in have:
            return False, f"{b} was never audited - run audit_claims.py on the folder"
        if have[b] != _sha(d):
            return False, f"{b} changed after its audit - run audit_claims.py on the folder again"
    return True, f"audit PASS on {rec.get('date', '?')} ({len(docs)} file(s))"


def _short(path):
    return os.path.basename(os.path.dirname(os.path.abspath(path)))[:40] + "/" + os.path.basename(path)[:28]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = sys.argv[1:] or ["."]
    bad = 0
    folders = {}
    for a in args:
        files = [a] if a.endswith(".docx") else sorted(glob.glob(os.path.join(a, "**", "*.docx"), recursive=True))
        for f in files:
            pr = check(f)
            bad += bool(pr)
            folders.setdefault(os.path.dirname(os.path.abspath(f)), []).append((f, bool(pr)))
            print(("FAIL  " if pr else "PASS  ") + _short(f) + ("  | " + "; ".join(pr) if pr else ""))
    total = sum(len(v) for v in folders.values())
    for folder, items in folders.items():
        all_docs = {os.path.abspath(d) for d in glob.glob(os.path.join(folder, "*.docx"))}
        audited = {os.path.abspath(f) for f, _ in items}
        if not any(failed for _, failed in items) and audited >= all_docs:
            # a clean run covering every .docx in the folder -> the pass marker decide.py BUILT needs
            write_pass(folder, sorted(audited)); print(f"      {PASS_FILE} written in {os.path.basename(folder)}")
        elif any(failed for _, failed in items) and os.path.exists(os.path.join(folder, PASS_FILE)):
            try:
                os.remove(os.path.join(folder, PASS_FILE)); print(f"      {PASS_FILE} removed from {os.path.basename(folder)} (a file failed)")
            except OSError:
                pass
    print(f"\n{total - bad}/{total} clean")
    sys.exit(1 if bad else 0)
