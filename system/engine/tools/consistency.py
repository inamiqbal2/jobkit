#!/usr/bin/env python3
"""CONSISTENCY - same-company cross-check.
A recruiter who holds two of the user's resumes must not read two different stories about the same
employer, teaching, or publications. Given a NEW application folder, find every PRIOR application to
the same company in tracking/state.db ("Resume Used" paths), pull the story lines from each docx and
diff them side by side.

Which story lines: My Job Search/profile/approved_claims.yaml -> consistency_items, each
  {label, kind: entry_bullets | bullet_contains | line_startswith, match: [substrings]}
Default when the list is empty: the Publications line only.

Usage:  <jobkit python> tools/consistency.py applications/<Folder>
Verdict per item per prior resume: PASS (identical, or absent on both) / DIFF.
Exit 1 if any DIFF, 2 if no prior resumes could be read."""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import sys, os, re, sqlite3, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT, build as _build_cfg
import approved_claims as _ac

DB = os.path.join(ROOT, "tracking", "state.db")
_B = _build_cfg()
RESUME = _B["cv_filename"] if _B["format"] == "academic_cv" else _B["resume_filename"]   # 2026-10-09: CV mode compares CVs
_SKIP = re.compile(r"^\s*(#|SOURCE:|APPLY:|URL:|FIT:|Verified|Posted|=+|-+\s*$)", re.I)

ITEMS = list(_ac.CONSISTENCY_ITEMS) or [{"label": "Publications line", "kind": "line_startswith", "match": ["publications"]}]
LABELS = [it["label"] for it in ITEMS]


def company_of(folder):
    """Company name candidates: the JD's first content line ('Title | Company | ...' -> Company)
    and the folder-name prefix (CamelCase split into words)."""
    cands = []
    jd = os.path.join(folder, "JobDescription.txt")
    if os.path.exists(jd):
        for line in open(jd, encoding="utf-8", errors="ignore"):
            if line.strip() and not _SKIP.match(line):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2:
                    cands.append(parts[1])
                break
    prefix = os.path.basename(folder.rstrip("/")).split("_")[0]
    cands.append(prefix)
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", prefix)
    if spaced != prefix:
        cands.append(spaced)
    seen, out = set(), []
    for c in cands:
        c = c.strip()
        if c and c.lower() not in seen:
            seen.add(c.lower()); out.append(c)
    return out


def prior_rows(folder):
    """Rows in state.db for the same company, excluding the folder itself."""
    if not os.path.exists(DB):
        print(f"no db at {DB}"); return []
    c = sqlite3.connect(DB)
    me = os.path.basename(folder.rstrip("/"))
    rows, seen = [], set()
    for cand in company_of(folder):
        q = 'SELECT "#",Company,Position,"Date Applied",Status,"Resume Used" FROM applications ' \
            'WHERE Company LIKE ? ORDER BY CAST("#" AS INTEGER)'
        for r in c.execute(q, (f"%{cand}%",)):
            if r[0] in seen or (r[5] and me in r[5]):
                continue
            seen.add(r[0]); rows.append(r)
    if not rows:
        pref = re.sub(r"[^a-z0-9]", "", me.split("_")[0].lower())
        q = 'SELECT "#",Company,Position,"Date Applied",Status,"Resume Used" FROM applications ORDER BY CAST("#" AS INTEGER)'
        for r in c.execute(q):
            key = re.sub(r"[^a-z0-9]", "", (r[1] or "").lower())
            # same company only: equal normalized names, or one is the other plus a suffix of <= 4 characters ("acmeinc");
            # a shared 6-letter prefix ("denverwater" vs "denverhealth") is NOT the same employer (audit v0.4 bug 9)
            same=bool(pref) and (key==pref or (key.startswith(pref) and len(key)-len(pref)<=4) or (pref.startswith(key) and len(pref)-len(key)<=4 and len(key)>=6))
            if same and not (r[5] and me in r[5]) and r[0] not in seen:
                seen.add(r[0]); rows.append(r)
    return rows


def resume_path(resume_used):
    """'Resume Used' -> local docx path. Accepts file:///.../applications/X/<RESUME>,
    'applications/X', 'applications/X (note)'. Returns (path or None, folder)."""
    m = re.search(r"applications/([A-Za-z0-9_\-]+)", resume_used or "")
    if not m:
        return None, None
    fold = m.group(1)
    for p in (os.path.join(ROOT, "applications", fold, RESUME),
              re.sub(r"^file://", "", resume_used).split(" ")[0]):
        if p.endswith(".docx") and os.path.exists(p):
            return p, fold
    return None, fold


def extract(path):
    """The configured story items from one docx."""
    import docxtext   # v0.8: all text channels
    paras = [(p.text.strip(), p.style.name) for p, _ in docxtext.paragraphs(path)]
    out = {k: [] for k in LABELS}

    def bullets_after(i):
        j = i + 1
        if j < len(paras) and paras[j][1] != "List Bullet":
            j += 1
        got = []
        while j < len(paras) and paras[j][1] == "List Bullet":
            got.append(paras[j][0]); j += 1
        return got

    for i, (t, st) in enumerate(paras):
        if not t:
            continue
        low = t.lower()
        is_org = st != "List Bullet" and "\t" in t and i + 1 < len(paras) and paras[i + 1][1] != "List Bullet"
        is_title = st != "List Bullet" and "\t" not in t and i + 1 < len(paras) and paras[i + 1][1] == "List Bullet"
        for it in ITEMS:
            lab, kind = it["label"], it.get("kind", "bullet_contains")
            matches = [m.lower() for m in (it.get("match") or [])]
            hit = any(m in low for m in matches)
            if kind == "entry_bullets" and (is_org or is_title) and hit:
                out[lab] += bullets_after(i)
            elif kind == "bullet_contains" and st == "List Bullet" and hit and t not in out[lab]:
                out[lab].append(t)
            elif kind == "line_startswith" and any(low.startswith(m) for m in matches):
                out[lab].append(t)
    return {k: "\n".join(dict.fromkeys(v)) for k, v in out.items()}


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def word_diff(a, b):
    aw, bw = norm(a).split(), norm(b).split()
    frags = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, aw, bw).get_opcodes():
        if op == "equal":
            continue
        frags.append(f"[{' '.join(aw[i1:i2]) or '-'}] -> [{' '.join(bw[j1:j2]) or '-'}]")
    return frags


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    folder = sys.argv[1].rstrip("/")
    if not os.path.isabs(folder):
        folder = os.path.join(ROOT, folder) if not os.path.exists(folder) else os.path.abspath(folder)
    new_docx = os.path.join(folder, RESUME)
    if not os.path.exists(new_docx):
        print(f"no {RESUME} in {folder}"); return 2
    new = extract(new_docx)
    print(f"=== CONSISTENCY: {os.path.basename(folder)}  (company keys: {company_of(folder)})")
    rows = prior_rows(folder)
    if not rows:
        print("no prior applications to this company in state.db -> nothing to compare"); return 0
    any_diff, readable = False, 0
    for num, comp, pos, date, status, used in rows:
        path, fold = resume_path(used)
        print(f"\n--- prior row {num}: {comp} | {pos} | applied {date} | {status}")
        if not path:
            print(f"    resume NOT FOUND for 'Resume Used' = {used!r} (folder {fold}) -> skipped")
            continue
        readable += 1
        old = extract(path)
        for k in LABELS:
            a, b = norm(old[k]), norm(new[k])
            verdict = "PASS" if a == b else "DIFF"
            any_diff |= verdict == "DIFF"
            print(f"  [{verdict}] {k}")
            if verdict == "DIFF" or a:
                print(f"      prior ({(fold or '')[:40]}): {old[k] or '(absent)'}")
                print(f"      new   ({os.path.basename(folder)[:40]}): {new[k] or '(absent)'}")
            if verdict == "DIFF" and a and b:
                for fr in word_diff(a, b)[:8]:
                    print(f"        {fr}")
    if not readable:
        print("\nno prior resume file could be read"); return 2
    print(f"\nRESULT: {'DIFF - reconcile before sending' if any_diff else 'PASS - stories consistent'}")
    return 1 if any_diff else 0


if __name__ == "__main__":
    sys.exit(main())
