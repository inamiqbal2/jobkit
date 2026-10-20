#!/usr/bin/env python3
"""STATE — single source of truth for the pipeline (built 2026-08-28 restructure).
SQLite at tracking/state.db. jobs.csv (what the user reads) is a GENERATED VIEW: edit the db via this
CLI, then export. Round-trip validated at import time.

  <jobkit python> tools/state.py import-csv        # one-time: build db from tracking/jobs.csv
  <jobkit python> tools/state.py export-csv        # regenerate tracking/jobs.csv from db
  <jobkit python> tools/state.py stats             # computed board (status/lane/tier/size)
  <jobkit python> tools/state.py set <row#> col=value [col=value...]   # e.g. set 29 Status=interviewing
  <jobkit python> tools/state.py add k=v k=v ...   # new application (auto row#)
  <jobkit python> tools/state.py tracker           # (v0.4) rewrite <workspace>/tracker.csv, the plain-English view the person reads
  <jobkit python> tools/state.py applied "<employer>" [Position=..] ["Job Link"=..] [Channel=..]   # "I applied to <employer>"
  <jobkit python> tools/state.py outcome "<employer>" rejected|interview ["note"]                  # "<employer> rejected me" / "wants an interview"
tracker.csv is regenerated after EVERY change made through this file (set / add / applied / outcome) and by
decide.py after a BUILT or WATCH decision, so it always reflects the ledger. Never hand-edit it; it is a view.
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import sqlite3, csv, sys, os, datetime, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT, lane_names as _lane_names, TRACKER_CSV, APPLICATIONS   # JOBKIT: workspace = data root
DB=os.path.join(ROOT,"tracking","state.db"); CSV=os.path.join(ROOT,"tracking","jobs.csv")
LEDGER=os.path.join(ROOT,"tracking","dispositions.jsonl"); OUTCOMES=os.path.join(ROOT,"tracking","OUTCOMES_LOG.md")
COLS=['#','Company','Location','Position','Date Posted','Date Applied','Application ID','Job ID',
 'Rejection/Interview','Reject Type','Tier','Lane','Sector','Fit','Cov%','Yrs Bar','Custom Ans','Salary Range','Days to Resp',
 'Status','Outreach','Resume Used','Job Link',
 'Channel',   # 2026-09-12: how it was submitted - company-ATS | LinkedIn Easy Apply | Indeed | referral | email
 'Notes']     # v0.4: free text the person adds ("recruiter called 10/14"); shown in tracker.csv
Q=lambda c:'"'+c.replace('"','""')+'"'
# CANONICAL LANES. Lane labels drift when they are typed by hand (the same lane spelled four ways silently breaks
# every per-lane statistic), so a row's Lane must be one of settings.yaml lanes[].name; anything else warns.
CANONICAL_LANES = _lane_names()   # JOBKIT: settings.yaml lanes[].name; empty tuple = no lane check

def check_lane(v):
    if v and CANONICAL_LANES and v not in CANONICAL_LANES:
        import sys as _s
        print(f"WARNING: lane '{v}' is not canonical. Use one of: {', '.join(CANONICAL_LANES)}", file=_s.stderr)
    return v

def conn():
    c=sqlite3.connect(DB)
    c.execute(f"CREATE TABLE IF NOT EXISTS applications ({','.join(Q(x)+' TEXT' for x in COLS)}, PRIMARY KEY ({Q('#')}))")
    have={r[1] for r in c.execute("PRAGMA table_info(applications)")}
    for col in COLS:                       # schema migration: add any column missing from an older db
        if col not in have:
            c.execute(f"ALTER TABLE applications ADD COLUMN {Q(col)} TEXT DEFAULT ''"); c.commit()
    return c
def import_csv():
    c=conn(); rows=list(csv.DictReader(open(CSV, encoding="utf-8")))
    for r in rows:
        r.setdefault('Outreach','')
        c.execute(f"INSERT OR REPLACE INTO applications ({','.join(Q(x) for x in COLS)}) VALUES ({','.join('?'*len(COLS))})",
                  [r.get(k,'') for k in COLS])
    c.commit()
    n=c.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    print(f"imported {len(rows)} csv rows -> {n} db rows")
    export_csv(verify_against=rows)
def export_csv(verify_against=None):
    c=conn()
    rows=[dict(zip(COLS,r)) for r in c.execute(f"SELECT {','.join(Q(x) for x in COLS)} FROM applications ORDER BY CAST({Q('#')} AS INTEGER)")]
    with open(CSV,'w',newline='', encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=COLS); w.writeheader(); w.writerows(rows)
    if verify_against is not None:
        back=list(csv.DictReader(open(CSV, encoding="utf-8")))
        for a,b in zip(verify_against,back):
            for k in a:
                if k=='Outreach': continue
                assert a.get(k,'')==b.get(k,''), f"ROUND-TRIP MISMATCH row {a.get('#')} col {k!r}: {a.get(k)!r} != {b.get(k)!r}"
        print(f"round-trip VERIFIED: {len(back)} rows identical (+ new Outreach column)")
    else:
        print(f"exported {len(rows)} rows -> jobs.csv")
    try: tracker(quiet=True)
    except Exception as e: print(f"tracker.csv not updated: {type(e).__name__}: {e}", file=sys.stderr)

# ---- v0.4: tracker.csv - the plain-English view ---------------------------------------------------------------------
TRACKER_COLS=["Employer","Role","Location","Posted","Applied","Status","Outcome","Salary","Fit","Official link","Documents folder","Notes"]
_STATUS_WORDS={"open":"applied - waiting","applied":"applied - waiting","interviewing":"interviewing","advanced":"advanced","closed":"closed",
               "rejected":"rejected","withdrawn":"withdrawn","offer":"offer"}
def _canon(u):
    try:
        from urlcanon import canon; return canon(u or "")
    except Exception: return (u or "").strip().rstrip("/")
def _built_folders():
    """applications/<Folder>/JobDescription.txt headers -> {canon url: (folder, employer, title)}. Built documents the person
    has not applied with yet appear in the tracker from here (the db only holds applications)."""
    out={}
    if not os.path.isdir(APPLICATIONS): return out
    for d in sorted(os.listdir(APPLICATIONS)):
        jd=os.path.join(APPLICATIONS,d,"JobDescription.txt")
        if not os.path.isfile(jd): continue
        try: head=open(jd,encoding="utf-8",errors="replace").read(2000)
        except OSError: continue
        import re as _re
        src=_re.search(r"^SOURCE:\s*([^|\n]+)",head,_re.M); url=_re.search(r"^APPLY:\s*(\S+)",head,_re.M)
        emp=(src.group(1).strip() if src else d.split("_",1)[0])
        title=_words(d.split("_",1)[1]) if "_" in d else ""
        key=_canon(url.group(1)) if url else "folder:"+d
        out[key]=(os.path.join("applications",d),emp,title)
    return out
def _ledger():
    try: lines=[l for l in open(LEDGER,encoding="utf-8") if l.strip()]
    except FileNotFoundError: return []
    out=[]
    for l in lines:   # v0.9 (audit H8): one unreadable line (a crash mid-append) must not stop the whole system
        try: out.append(json.loads(l))
        except ValueError: print(f"ledger: skipping one unreadable line in dispositions.jsonl ({l[:60]!r})",file=sys.stderr)
    return out
_EMP_COLON=__import__("re").compile(r"^([A-Z][^:]{2,80}?):\s+(.+)$")
_EMP_AT=__import__("re").compile(r"^(.+?)\s+(?:at|@)\s+([A-Z][^|]{2,80})$")
_EMP_DASH=__import__("re").compile(r"^(.+?)\s+[-|\u2013\u2014]\s+([A-Z][A-Za-z0-9&'.,\- ]{2,80})$")
def split_employer(src,title):
    """(employer, role) for a posting. Official arms (a company's own board) name the employer in src. A listing FEED
    (RSS boards such as the Chronicle, HigherEdJobs, VC boards, listserv archives) names the FEED in src and carries the
    employer inside the title ("Employer: Role", "Role at Employer", "Role - Employer"); the tracker must show the
    employer, never the feed (audit v0.4 finding 22). Aggregator prefixes (li: / in: / adzuna:) are stripped."""
    src=str(src or ""); title=str(title or "").strip()
    low=src.lower()
    for pre in ("li:","in:","adzuna:","sr:","misc:","custom:","getro:"):
        if low.startswith(pre):
            emp=src[len(pre):].strip()
            if pre in ("getro:","misc:","custom:"):   # a board / small-ATS name, not necessarily the employer
                m=_EMP_COLON.match(title) or _EMP_AT.match(title)
                if m and pre=="getro:": return (m.group(1).strip() if m.re is _EMP_COLON else m.group(2).strip()), (m.group(2).strip() if m.re is _EMP_COLON else m.group(1).strip())
            return emp,title
    if _FEED_NAMES and src in _FEED_NAMES:
        m=_EMP_COLON.match(title)
        if m and len(m.group(1).split())<=8: return m.group(1).strip(),m.group(2).strip()
        m=_EMP_AT.match(title)
        if m and len(m.group(2).split())<=8: return m.group(2).strip(),m.group(1).strip()
        m=_EMP_DASH.match(title)
        if m and len(m.group(2).split())<=6: return m.group(2).strip(),m.group(1).strip()
        return "",title                     # unknown employer: better empty than the feed's name
    return src,title
def _feed_names():
    try:
        reg=json.load(open(os.path.join(ROOT,"tracking","registries","feeds_registry.json"),encoding="utf-8"))
        return {str(e.get("name","")) for e in (reg.get("feeds") or []) if isinstance(e,dict)}|{"usajobs"}
    except Exception: return set()
_FEED_NAMES=_feed_names()
def _seen_postings():
    """{canon url: (employer, title, loc, posting url)} from the pipeline's screened / candidate lists, so WATCH rows carry a name
    and the posting's own link."""
    out={}
    for name in ("minquals_screened.json","candidates.json","feed_candidates.json","hard_candidates.json"):
        fp=os.path.join(ROOT,"tracking",name)
        try: items=json.load(open(fp,encoding="utf-8"))
        except (OSError,ValueError): continue
        for x in (items if isinstance(items,list) else []):
            u=_canon(x.get("url"))
            if u and u not in out:
                emp,role=split_employer(x.get("src") or x.get("company",""),x.get("title",""))
                out[u]=(emp,role,x.get("loc",""),x.get("url",""))
    return out
def _words(camel):
    """DenverHealth_RegisteredNurse_MedicalICU -> 'Registered Nurse Medical ICU' (role part only)."""
    import re as _re
    return _re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"," ",camel).replace("_"," ").strip()
def tracker(quiet=False):
    """Write <workspace>/tracker.csv: every application row from the db in plain columns, then every BUILT / WATCH ledger item
    the person has not applied to yet (status 'built - not applied yet' / 'watching'). Pure view: never read back."""
    c=conn()
    rows=[dict(zip(COLS,r)) for r in c.execute(f"SELECT {','.join(Q(x) for x in COLS)} FROM applications ORDER BY CAST({Q('#')} AS INTEGER) DESC")]
    folders=_built_folders(); seen=set(); out=[]
    for r in rows:
        st=(r.get("Status") or "").strip().lower(); status=_STATUS_WORDS.get(st, st or "applied - waiting")
        _rt=(r.get("Reject Type") or "").strip(); _rt="" if _rt.upper()=="UNKNOWN" else _rt   # UNKNOWN is internal jargon (audit v0.4 section 4)
        outcome=" ".join(x for x in ((r.get("Rejection/Interview") or "").strip(),_rt) if x)
        doc=r.get("Resume Used") or ""; folder=os.path.dirname(doc) if doc else ""
        if folder and os.path.isabs(folder):
            try: folder=os.path.relpath(folder,ROOT)
            except ValueError: pass
        key=_canon(r.get("Job Link"))
        if key: seen.add(key)
        if not folder and key in folders: folder=folders[key][0]
        out.append({"Employer":r.get("Company",""),"Role":r.get("Position",""),"Location":r.get("Location",""),"Posted":r.get("Date Posted",""),
                    "Applied":r.get("Date Applied",""),"Status":status,"Outcome":outcome,"Salary":r.get("Salary Range",""),"Fit":r.get("Fit",""),
                    "Official link":r.get("Job Link",""),"Documents folder":folder,"Notes":r.get("Notes","")})
    last={}
    for d in _ledger(): last[d.get("url")]=d            # last decision per url wins (REOPEN supersedes)
    known=_seen_postings() if any(d.get("decision")=="WATCH" for d in last.values()) else {}
    for url,d in sorted(last.items(), key=lambda kv: kv[1].get("date",""), reverse=True):
        dec=d.get("decision")
        if dec not in ("BUILT","WATCH") or url in seen: continue
        f=folders.get(url); k=known.get(url,("","","",""))
        out.append({"Employer":f[1] if f else k[0],"Role":f[2] if f else k[1],"Location":k[2],"Posted":"","Applied":"",
                    "Status":"built - not applied yet" if dec=="BUILT" else "watching","Outcome":"","Salary":"","Fit":"",
                    "Official link":d.get("raw_url") or k[3] or url,"Documents folder":f[0] if f else "","Notes":(d.get("reason") or "")[:160]})
    with open(TRACKER_CSV,"w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=TRACKER_COLS); w.writeheader(); w.writerows(out)
    if not quiet: print(f"tracker.csv: {len(out)} rows ({len(rows)} applications) -> {TRACKER_CSV}")
    return len(out)
def _find_rows(employer):
    """Every db row whose Company contains the words given (case-insensitive), newest first."""
    c=conn(); needle=(employer or "").strip().lower(); out=[]
    for r in c.execute(f"SELECT {','.join(Q(x) for x in COLS)} FROM applications ORDER BY CAST({Q('#')} AS INTEGER) DESC"):
        row=dict(zip(COLS,r))
        if needle and needle in (row.get("Company") or "").lower(): out.append(row)
    return out
class Ambiguous(Exception):
    """More than one employer matches the words given: Claude must ask which one (audit v0.4 bug 9)."""
def _one_company(employer,rows):
    """The rows of ONE company, or raise Ambiguous listing the candidates."""
    comps=[]
    for r in rows:
        if (r.get("Company") or "") not in comps: comps.append(r.get("Company") or "")
    if len(comps)>1:
        raise Ambiguous(f"'{employer}' matches more than one employer: {', '.join(comps)}. Which one?")
    return rows
def _find_row(employer):
    rows=_one_company(employer,_find_rows(employer))
    return rows[0] if rows else None
def _log_outcome(line):
    os.makedirs(os.path.dirname(OUTCOMES),exist_ok=True)
    new=not os.path.exists(OUTCOMES)
    with open(OUTCOMES,"a",encoding="utf-8") as f:
        if new: f.write("# OUTCOMES LOG (narrative journal; numbers come from report.py / timeline.py)\n\n")
        f.write(f"- {datetime.date.today().isoformat()} {line}\n")
def _learning_columns(url, given):
    """v0.9 (audit H2): the analysis columns report.py / timeline.py group on, filled from what the engine already knows
    about this posting (minquals_screened.json: tier, fit class, age, salary band, years bar; the rubric score; the lane the
    critic's lane_rules give the text). Nothing the person said is overwritten (`given` wins)."""
    out={}
    if not url: return out
    try:
        from urlcanon import canon as _canon_url
        cu=_canon_url(url)
        import datetime as _dt
        rec=None
        for x in json.load(open(os.path.join(ROOT,"tracking","minquals_screened.json"),encoding="utf-8")):
            if _canon_url(x.get("url","") or "")==cu: rec=x; break
        if rec:
            if rec.get("tier"): out["Tier"]="T"+str(rec["tier"])
            if rec.get("fitclass"): out["Fit"]=f"{rec['fitclass']}"+(f" {rec['rubric']:g}" if rec.get("rubric") is not None else "")
            if rec.get("age") not in (None,""):
                try: out["Date Posted"]=(_dt.date.today()-_dt.timedelta(days=int(rec["age"]))).isoformat()
                except Exception: pass
            if rec.get("band_lo") and rec.get("band_hi"): out["Salary Range"]=f"${rec['band_lo']/1000:.0f}-{rec['band_hi']/1000:.0f}K"
            if rec.get("yrs"): out["Yrs Bar"]=str(min(rec["yrs"]))
            try:
                from critic import lane_of as _lane_of
                _t=open(rec["jd"],encoding="utf-8",errors="ignore").read() if rec.get("jd") else ""
                _l=_lane_of(_t) if _t else None
                if _l: out["Lane"]=_l
            except Exception: pass
    except Exception: pass
    return {k:v for k,v in out.items() if k not in (given or {})}


def applied(employer,pairs):
    """'I applied to <employer>': set Date Applied / Status / Channel on the open row for that employer, or create the row
    from the built application folder (Position, Job Link, Resume Used filled from the folder when not given).
    IDEMPOTENT (audit v0.4 bug 8): a second call for the same posting says "already recorded on <date>" and changes nothing
    (extra Position= / Job Link= / Channel= / Notes= values given on the repeat call update that row).
    AMBIGUOUS names (bug 9): more than one employer matching -> the candidates are listed and nothing is written (exit 2)."""
    today=datetime.date.today().isoformat(); given={}
    for p in pairs:
        k,v=p.split("=",1); assert k in COLS, f"unknown column {k}"; given[k]=v
    needle=(employer or "").strip().lower()
    # the built folders for this employer (one employer may have several postings -> Position / Job Link disambiguate)
    matches=[(key,folder,emp,title) for key,(folder,emp,title) in _built_folders().items() if needle and (needle in emp.lower() or needle in folder.lower())]
    emps=[]
    for _,_,emp,_ in matches:
        if emp not in emps: emps.append(emp)
    rows=_find_rows(employer)
    for r_ in rows:
        if (r_.get("Company") or "") not in emps: emps.append(r_.get("Company") or "")
    if len(emps)>1:
        print(f"'{employer}' matches more than one employer: {', '.join(emps)}. Which one? (nothing recorded)"); return 2
    if given.get("Job Link"): matches=[m for m in matches if _canon(given["Job Link"])==m[0]] or matches
    if given.get("Position"): matches=[m for m in matches if given["Position"].lower() in m[3].lower()] or matches
    if len(matches)>1:
        print(f"{employer} has {len(matches)} built postings: "+"; ".join(f"{t} ({f})" for _,f,_,t in matches)+". Which one? Say the position or the link. (nothing recorded)"); return 2
    match=matches[0] if matches else None
    # already recorded? (same posting link, or same company + position, with a Date Applied)
    for r_ in rows:
        same_link=match and r_.get("Job Link") and _canon(r_["Job Link"])==match[0]
        same_pos=(not match or not r_.get("Job Link")) and (not given.get("Position") or given["Position"].lower()==(r_.get("Position") or "").lower())
        if r_.get("Date Applied") and (same_link or (same_pos and (not match or (r_.get("Position") or "").lower()==match[3].lower()) and (r_.get("Company") or "").lower()==(match[2] if match else employer).lower())):
            upd=[f"{k}={v}" for k,v in given.items()]
            if upd: set_row(r_["#"],upd)
            print(f"{r_.get('Company')} - {r_.get('Position')}: already recorded as applied on {r_['Date Applied']} (row {r_['#']})"+(f"; updated {', '.join(upd)}." if upd else "; nothing changed.")); return 0
    row=next((r_ for r_ in rows if (r_.get("Status") or "").lower() in ("","open","built") and not r_.get("Date Applied")),None)
    if row:
        pairs=[f"Date Applied={today}","Status=open",f"Channel={given.get('Channel','company-ATS')}"]+[f"{k}={v}" for k,v in given.items() if k!="Channel"]
        set_row(row["#"],pairs); _log_outcome(f"APPLIED {row.get('Company')} - {row.get('Position')} (row {row['#']})"); return 0
    # new row: fill from the built folder for that employer
    r={"Company":employer,"Date Applied":today,"Status":"open","Channel":"company-ATS"}
    if match:
        key,folder,emp,title=match; r["Company"]=emp; r["Position"]=title
        if not key.startswith("folder:"): r["Job Link"]=key
        docs=[x for x in os.listdir(os.path.join(ROOT,folder)) if x.lower().endswith(".docx")]
        if docs: r["Resume Used"]=os.path.join(folder,sorted(docs)[0])
    r.update(_learning_columns(r.get("Job Link") or "", given))   # v0.9 (audit H2): Tier / Lane / Fit / Date Posted / Salary / Yrs Bar
    r.update(given)
    add([f"{k}={v}" for k,v in r.items()])
    if match and r.get("Job Link"):
        with open(LEDGER,"a",encoding="utf-8") as f:
            f.write(json.dumps(dict(date=today,url=r["Job Link"],decision="APPLIED",reason="the person applied on the employer site"))+"\n")
    _log_outcome(f"APPLIED {r['Company']} - {r.get('Position','')}"); return 0
def outcome(employer,kind,note=""):
    """'<employer> rejected me' / '<employer> wants an interview': Status + Rejection/Interview + Days to Resp + OUTCOMES_LOG."""
    kind=kind.lower(); assert kind in ("rejected","interview"), "kind must be rejected|interview"
    try: row=_find_row(employer)
    except Ambiguous as e: print(f"{e} (nothing recorded)"); return 2
    if not row: print(f"no application row for '{employer}' - say 'I applied to {employer}' first"); return 1
    today=datetime.date.today()
    days=""
    try: days=str((today-datetime.date.fromisoformat(row.get("Date Applied") or "")).days)
    except ValueError: pass
    if kind=="rejected":
        # v0.9 (M16): the note may carry the one classification learning needs - "filled" / "timing" (position gone, no human read it)
        # vs "fit" / "merit" (a person read it and passed); otherwise UNKNOWN until the person says
        _rt="UNKNOWN"
        if re.search(r"\b(filled|closed|timing|no longer|withdrawn)\b",note or "",re.I): _rt="TIMING"
        elif re.search(r"\b(fit|merit|qualif|experience|not a match|another candidate)\b",note or "",re.I): _rt="MERIT"
        pairs=["Status=rejected",f"Rejection/Interview={today.isoformat()} rejection",f"Reject Type={_rt}"]
    else:
        pairs=["Status=interviewing",f"Rejection/Interview={today.isoformat()} interview"]
    if days: pairs.append(f"Days to Resp={days}")
    if note: pairs.append(f"Notes={note}")
    set_row(row["#"],pairs)
    _log_outcome(f"{kind.upper()} {row.get('Company')} - {row.get('Position')} (row {row['#']}, {days or '?'} days after applying){(': '+note) if note else ''}")
    return 0
def stats():
    c=conn(); g=lambda q: c.execute(q).fetchall()
    print("STATUS:",dict(g("SELECT Status,COUNT(*) FROM applications GROUP BY Status")))
    print("\nLANE (responded only):")
    for lane,n,pos,neg in g("""SELECT Lane,COUNT(*),
        SUM(CASE WHEN Status IN ('interviewing','advanced','offer') THEN 1 ELSE 0 END),
        SUM(CASE WHEN Status='rejected' THEN 1 ELSE 0 END)
        FROM applications WHERE Lane!='' GROUP BY Lane"""):
        print(f"  {lane:16} applied {n:2} | +{pos or 0} / -{neg or 0}")
    print("\nTIER:",dict(g("SELECT Tier,COUNT(*) FROM applications GROUP BY Tier")))
    print("FIT:",dict(g("SELECT Fit,COUNT(*) FROM applications WHERE Fit!='' GROUP BY Fit")))
def set_row(num,pairs):
    c=conn()
    for p in pairs:
        k,v=p.split('=',1)
        assert k in COLS, f"unknown column {k}"
        if k=='Lane': check_lane(v)
        c.execute(f"UPDATE applications SET {Q(k)}=? WHERE {Q('#')}=?",(v,num))
    c.commit(); export_csv(); print(f"row {num} updated: {pairs}")
def add(pairs):
    c=conn()
    n=(c.execute(f"SELECT MAX(CAST({Q('#')} AS INTEGER)) FROM applications").fetchone()[0] or 0)+1
    r={k:'' for k in COLS}; r['#']=str(n); r['Status']='open'
    for _p in pairs:
        if _p.startswith('Lane='): check_lane(_p.split('=',1)[1])
    for p in pairs:
        k,v=p.split('=',1); assert k in COLS, f"unknown column {k}"; r[k]=v
    c.execute(f"INSERT INTO applications ({','.join(Q(x) for x in COLS)}) VALUES ({','.join('?'*len(COLS))})",[r[k] for k in COLS])
    c.commit(); export_csv(); print(f"row {n} added")
if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "stats"
    if cmd=="import-csv": import_csv()
    elif cmd=="export-csv": export_csv()
    elif cmd=="stats": stats()
    elif cmd=="set": set_row(sys.argv[2],sys.argv[3:])
    elif cmd=="add": add(sys.argv[2:])
    elif cmd=="tracker": tracker()
    elif cmd=="applied": sys.exit(applied(sys.argv[2],sys.argv[3:]) or 0)
    elif cmd=="outcome": sys.exit(outcome(sys.argv[2],sys.argv[3],sys.argv[4] if len(sys.argv)>4 else "") or 0)
    else: print(__doc__)
