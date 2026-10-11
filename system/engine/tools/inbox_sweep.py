#!/usr/bin/env python3
"""INBOX SWEEP — OPTIONAL read-only mailbox check (settings.yaml modules.inbox_sweep; OFF by default).

Purpose: on each pipeline run, check the user's mailbox (READ ONLY) for responses from employers they
applied to - rejections, next steps - and hand the findings to the judgment step.

WHY A PLAN FILE AND NOT AN API CALL: daily.py is a plain Python script and has no Gmail access.
The mailbox is reachable only through the agent's Gmail tools. So this module does the deterministic
half - work out WHO we are waiting on, for HOW long, and WHAT to search - and hands the agent an
explicit checklist. The agent then runs the searches READ-ONLY and records what it finds.

HARD RULE, stated here so it survives into future sessions:
  NEVER read an email whose sender does not correspond to a company the user has applied to. Every search is
  scoped with from:(<employer tokens>) - never a bare keyword search over the whole mailbox - and results are
  listed with view=THREAD_VIEW_METADATA_ONLY (no subject/snippet). A thread is opened only after its sender
  address/name is confirmed against the employer list. Unmatched senders are ignored, not previewed.
  (Trigger in the original project: a bare keyword search surfaced a personal legal email; that must not recur.)

HARD RULE, stated here so it survives into future sessions:
  READ ONLY. Never send, reply, draft-into-Gmail, label, archive, trash, or mark anything.
  Findings get logged to state.db and tracking/OUTCOMES_LOG.md. Replies are drafted in the repo as
  markdown for the user to approve, exactly as every other outbound message in this project.

Usage:
  <jobkit python> tools/inbox_sweep.py          # write today's sweep plan, print it
  <jobkit python> tools/inbox_sweep.py --quiet  # write the plan, print only the header
"""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import json, os, sqlite3, sys, datetime, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from userconfig import WS as ROOT, MODULES as _MODULES, path as _wspath   # JOBKIT: workspace = data root; module switch
DB    = os.path.join(ROOT, "tracking", "state.db")
STATE = os.path.join(ROOT, "tracking", "inbox_sweep_state.json")
TODAY = datetime.date.today().isoformat()

# Phrases that actually appear in the outcomes this pipeline has already seen.
KEYWORDS = ('interview OR "not selected" OR "not moving forward" OR "move forward" OR '
            '"other candidates" OR "unfortunately" OR "thank you for applying" OR '
            '"your application" OR "next steps" OR availability OR recruiter OR '
            '"schedule" OR offer OR "keep your resume"')

# Sender tokens for mailbox from: matching (matches address OR display name). Default = first significant word
# of the company name. Overrides (employer name -> domain-form token) are WORKSPACE data:
# tracking/inbox_sender_tokens.json  {"acme chemical": "acmechem.com OR acme", ...}. Use domain-form tokens for
# employers whose plain name is also a surname or a consumer brand, so personal senders never match.
try: _TOK_OVERRIDE = {str(k).lower(): str(v) for k, v in json.load(open(_wspath("tracking", "inbox_sender_tokens.json"), encoding="utf-8")).items()}
except Exception: _TOK_OVERRIDE = {}
_STOP = {"the", "inc", "inc.", "llc", "corp", "corporation", "company", "co", "ltd", "group"}
def _token(name):
    n = (name or "").strip().lower()
    if not n: return ""
    if n in _TOK_OVERRIDE: return _TOK_OVERRIDE[n]
    for k, v in _TOK_OVERRIDE.items():
        if n.startswith(k): return v
    w = [x for x in re.split(r"[^a-z0-9-]+", n) if x and x not in _STOP]
    return w[0] if w else ""

def _last_sweep():
    try:
        return json.load(open(STATE, encoding="utf-8")).get("last_sweep")
    except Exception:
        return None

def _save_sweep(found):
    json.dump({"last_sweep": TODAY, "last_found": found},
              open(STATE, "w", encoding="utf-8"), indent=1)

def build_plan():
    last = _last_sweep()
    # Window: since the last sweep, with a 3-day overlap so nothing falls between runs.
    if last:
        d = (datetime.date.today() - datetime.date.fromisoformat(last)).days + 3
    else:
        d = 21
    days = max(3, min(d, 60))

    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = list(c.execute("""SELECT "#",Company,Position,Status,"Date Applied"
                             FROM applications
                             WHERE "Date Applied"!='' AND Status IN
                                   ('open','interviewing','advanced')"""))
    live = [r for r in rows if r["Status"] in ("interviewing", "advanced")]
    seen, companies = set(), []
    for r in rows:
        nm = re.sub(r"\s*\(.*?\)\s*", " ", r["Company"] or "").strip()
        key = nm.lower()
        if nm and key not in seen:
            seen.add(key); companies.append(nm)

    # 2026-10-01: sender-scoped only. One from:(...) clause per batch of employer tokens; no bare keywords.
    toks = sorted({_token(n) for n in companies if _token(n)})
    queries = []
    for i in range(0, len(toks), 25):
        grp = " OR ".join(toks[i:i+25])
        queries.append(f'newer_than:{days}d from:({grp})')
        queries.append(f'newer_than:{days}d in:spam from:({grp})')
    live_toks = sorted({_token(re.sub(r"\s*\(.*?\)\s*", " ", r["Company"] or "").strip()) for r in live})
    if live_toks:
        queries.append(f'newer_than:45d from:({" OR ".join(t for t in live_toks if t)})')
    return days, rows, live, companies, queries

def main():
    quiet = "--quiet" in sys.argv
    if not _MODULES.get("inbox_sweep"):
        print("inbox sweep: DISABLED (settings.yaml modules.inbox_sweep is false). Nothing read, nothing written.")
        return None
    days, rows, live, companies, queries = build_plan()
    out = os.path.join(ROOT, "tracking", f"inbox_sweep_{TODAY}.md")
    L = []
    L.append(f"# INBOX SWEEP PLAN — {TODAY}  (READ ONLY)")
    L.append(f"Window: last {days} days (since the previous sweep, +3 days of overlap).")
    L.append(f"Waiting on {len(rows)} applications; {len(live)} are live processes.\n")
    L.append("## Run these mailbox searches, read only - SENDER-SCOPED")
    L.append("Use view=THREAD_VIEW_METADATA_ONLY. Open a thread ONLY if its sender matches an employer below.")
    L.append("Never run a bare keyword search over the mailbox; never preview unmatched senders.")
    L.append("Consumer-facing employers (Amazon, Apple, Meta/Facebook, Intel, Pfizer, Merck, 3M, Tesla): open ONLY")
    L.append("recruiting senders (jobs/careers/recruiting/talent/workday/greenhouse/icims-type addresses) - never")
    L.append("orders, accounts, billing or marketing mail from the same company.")
    for q in queries:
        L.append(f"- `{q}`")
    L.append("\n## Live processes — a reply here is the highest-value find")
    for r in live:
        L.append(f"- row {r['#']:>3}  {r['Company']} — {r['Position'][:60]}  (applied {r['Date Applied']}, {r['Status']})")
    L.append("\n## Every employer with an application still open")
    L.append(", ".join(sorted(companies)))
    L.append("\n## What to do with a find")
    L.append("1. REJECTION -> state.py set <row> Status=rejected, record the date and days-to-response.")
    L.append("2. NEXT STEP (screen, interview, questionnaire, offer) -> update Rejection/Interview,")
    L.append("   set Status, and BUILD THE PREP before telling the user the date.")
    L.append("3. Anything needing a reply -> draft it in the repo as markdown. NEVER send from the mailbox.")
    L.append("4. Nothing found -> say so plainly; silence is data (replies can land weeks later; never infer ghosting early).")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"INBOX SWEEP PLAN -> {out}")
    print(f"  window {days}d | {len(rows)} open applications | {len(live)} live processes | {len(queries)} searches")
    if not quiet:
        print("\n".join(L[3:]))
    return out

if __name__ == "__main__":
    main()
