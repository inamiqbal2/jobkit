#!/usr/bin/env python3
"""Honesty audit for built documents. Run on EVERY .docx before it is shown to the person (CONSTITUTION I.1, I.8).
All claim boundaries come from My Job Search/profile/approved_claims.yaml (via approved_claims.py).

WHITELIST (since v0.5): a resume or CV is a list of approved sentences, nothing else.
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


import docxtext as _dx


def _kind(path, doc=None):
    """v0.8 (code audit H2): what a .docx IS decides how strictly it is audited, and the decision fails CLOSED.
    resume_builder stamps every resume / CV; the build skill stamps letters (docxtext.stamp_letter). A stamp wins. Without a
    stamp the configured filenames decide; a file with neither is audited as a RESUME - the strict path - never as a letter."""
    k = _dx.kind(doc if doc is not None else path)
    if k:
        return k
    base = os.path.basename(path).lower()
    if base == os.path.basename(str(_build_cfg().get("cv_filename", ""))).lower() or base.startswith("cv"):
        return "cv"
    if base == os.path.basename(str(_build_cfg().get("resume_filename", ""))).lower() or base.startswith("resume"):
        return "resume"
    if re.match(r"(coverletter|cover_letter|cover-letter|letter|statement)", base):
        return "letter"
    return "resume"


def _is_cv(path, doc=None):
    return _kind(path, doc) == "cv"


def _is_resume(path, doc=None):
    return _kind(path, doc) in ("resume", "cv")


def _norm_dates(d):
    return re.sub(r"\bSept\b\.?", "Sep", str(d or ""))


def _builder_footer_lines():
    """The only footer text a jobkit document may carry: the AcademicCV page footer (name + 'Curriculum Vitae')."""
    name = str(_cfg("identity.name", "") or "").strip()
    # resume_builder._page_footer writes "<name> - Curriculum Vitae - page " + a PAGE field; the field renders as a digit
    return [f"{name} - Curriculum Vitae - page", f"{name} - Curriculum Vitae - page 1", name] if name else []


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


# v0.8 (code audit H6): a heading is recognised by STRUCTURE - the bottom border resume_builder._heading draws under every
# section title - never by "any short ALL-CAPS line". A plain paragraph in capitals is a claim like any other.
from docx.oxml.ns import qn as _qn
def _is_builder_heading(q):
    pPr = q._p.pPr
    if pPr is None or pPr.find(_qn("w:pBdr")) is None:
        return False
    t = q.text.strip()
    return bool(t) and len(t.split()) <= 6 and not re.search(r"[.;:]|\d", t)
_PREFIX_OK = re.compile(r"^[A-Za-z][A-Za-z ,'&/()\-]{0,58}$")   # a role-noun opener: letters only, no digits, no claims with numbers


def _traceability(paras):
    """Untraceable paragraphs of a resume / CV (see module docstring). Returns a list of offending texts."""
    ok = _approved_set()
    n = _ac._norm
    labels = {n(l) for l, _ in {**_ac.SKILLS_LINES, **_ac.CV_SKILLS}.values()} | {n(c[0]) for c in _ac.CONSTANTS.values() if isinstance(c, tuple) and len(c) == 2} \
             | {n(_ac.PUBS[0]) if _ac.PUBS else ""} | {n(p["title"]) for p in _ac.PROJECTS.values() if isinstance(p, dict) and p.get("title")}
    summaries = {n(v) for v in _ac.SUMMARIES.values() if v}
    tenures = {n(t) for t in (_ac.TENURE, _ac.TENURE_SHORT) if t}
    name = str(_cfg("identity.name", "") or "").strip()
    phone = str(_cfg("identity.phone", "") or "").strip(); email = str(_cfg("identity.email", "") or "").strip()
    nonempty = [q for q in paras if q.text.strip()]
    bad = []
    try:
        from claim_lexicon import canonical as _lex   # 2026-10-16: confirmed equivalent wordings map back to approved wording
    except Exception:
        _lex = lambda x: x
    for i, q in enumerate(nonempty):
        t = _lex(q.text.strip())
        is_list = q.style.name.startswith("List")
        if name and t == name:
            continue                                            # name line (structure)
        if i == 1 and name and nonempty[0].text.strip() == name and (email in t or phone in t):
            continue                                            # contact line = the line right under the name, carrying the email or phone
        if _is_builder_heading(q) and not is_list:
            continue                                            # section heading = a paragraph the builder drew with its border
        tn = n(re.sub(r"^\d+\.\s*", "", t))                      # numbered publication
        if tn in ok:
            continue
        # "Label : approved text" - the label is structure, the text must be approved
        m = re.match(r"^([^:]{1,40}?)\s*:\s*(.+)$", t)
        if m and n(m.group(1)) in labels and n(m.group(2)) in ok:
            continue                                            # label = an approved label (skills line, constant, project title)
        # "<role noun prefix (<= 60 chars)>: <approved summary>[ <approved tenure line>]"
        body = tn.rstrip(" .;,")
        for tl in tenures:
            tl = tl.rstrip(" .;,")
            if body.endswith(" " + tl):
                body = body[: -len(tl) - 1].rstrip(" .;,")
        for sm in summaries:
            sm = sm.rstrip(" .;,")
            if body.endswith(sm):
                prefix = body[: -len(sm)].rstrip(" :")
                if not prefix or (len(prefix) <= 60 and _PREFIX_OK.match(prefix) and not re.search(r"\d", prefix)):
                    break
        else:
            bad.append(t[:80])
            continue
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
    try:
        doc = Document(path)
    except Exception as e:   # v0.8 (M9): an unreadable file is a FAIL line, never a traceback that aborts the folder
        return [f"unreadable .docx ({type(e).__name__}) - rebuild it"]
    # v0.8 (H1): EVERY text channel - body, tables, headers, footers, text boxes - not just body paragraphs
    located = _dx.paragraphs(doc)
    paras = [q for q, _ in located]
    t = " ".join(p.text for p in paras)
    is_resume = _is_resume(path, doc)
    offpage = [f"{where}: {q.text.strip()[:60]}" for q, where in located if where != "body" and q.text.strip()]
    if is_resume and offpage:
        # a resume / CV built by jobkit has no tables, headers or footers (the CV page footer is the builder's own and is
        # whitelisted below); anything else there is text the person did not approve
        own_footer = {_ac._norm(x) for x in _builder_footer_lines()}
        extra = [x for (q, where), x in zip([(q, w) for q, w in located if w != "body" and q.text.strip()], offpage)
                 if re.sub(r"\s*\d+$", "", _ac._norm(q.text.strip())).strip() not in own_footer]
        if extra:
            problems.append(f"text outside the page body (tables / headers / footers): {extra[:4]}")

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
        # the builder's own CV page footer is structure, not a claim (its text is whitelisted above); every other paragraph is checked
        _own = {_ac._norm(x) for x in _builder_footer_lines()}
        untraced = _traceability([q for q, where in located if not (where == "footer" and re.sub(r"\s*\d+$", "", _ac._norm(q.text.strip())).strip() in _own)])
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
    docs = sorted(d for d in glob.glob(os.path.join(folder, "*.docx")) if not _dx.is_stray(d))   # v0.9 (M24): ~$ lock files are not documents
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
        files = [f for f in files if not _dx.is_stray(f)]   # v0.8 (M9): Word lock files and .bak-<date> backups are not documents
        for f in files:
            pr = check(f)
            bad += bool(pr)
            folders.setdefault(os.path.dirname(os.path.abspath(f)), []).append((f, bool(pr)))
            print(("FAIL  " if pr else "PASS  ") + _short(f) + ("  | " + "; ".join(pr) if pr else ""))
    total = sum(len(v) for v in folders.values())
    for folder, items in folders.items():
        all_docs = {os.path.abspath(d) for d in glob.glob(os.path.join(folder, "*.docx")) if not _dx.is_stray(d)}
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
