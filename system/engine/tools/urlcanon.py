#!/usr/bin/env python3
"""URL canonicalization (2026-10-01 audit fix H3). One job must have ONE ledger key - and one key must be ONE job.
- host lower-case; boards.greenhouse.io -> job-boards.greenhouse.io
- tracking params dropped: utm_*, gh_src, source, ref, trk, refId, trackingId, position, pageNum, src, lipi, ...
- fragment dropped, trailing slash dropped; path case preserved (Workday paths are case-sensitive)
- query params that IDENTIFY THE JOB are KEPT, whatever the host: gh_jid (a Greenhouse job embedded on the employer's own
  site - audit v0.4 bug 4: dropping it collapsed 62 Achievement First postings into one key), jk (Indeed), jobId / job_id /
  jid / id / req / reqId / requisitionId / posting / postingId / lever / ashby_jid, and coreweave's bare id.
  Lever (jobs.lever.co/<co>/<uuid>), Ashby (jobs.ashbyhq.com/<co>/<uuid>) and Workday (.../job/<loc>/<title>_<req>) carry
  the id in the PATH, which is never touched."""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, quote
_DROP = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","gh_src","source","ref",
         "trk","refid","trackingid","position","pagenum","src","lipi","trkinfo","originalsubdomain","ccid"}
_KEEP = {"gh_jid","jk","jobid","job_id","jid","id","req","reqid","requisitionid","posting","postingid","lever","ashby_jid"}
def canon(url: str) -> str:
    if not url: return url
    u = url.strip()
    try:
        s = urlsplit(u)
    except Exception:
        return u
    host = (s.netloc or "").lower()
    # 2026-10-05: Adzuna links carry a per-API-call session token (se=) and signature (v=) - the same ad re-surfaced
    # as "new" on every run. One key per ad id: https://www.adzuna.com/details/<id>.
    _m = re.search(r"adzuna\.com/(?:land/ad|details)/(\d+)", u)
    if _m: return f"https://www.adzuna.com/details/{_m.group(1)}"
    if host == "boards.greenhouse.io": host = "job-boards.greenhouse.io"
    path = re.sub(r"/+$", "", s.path or "")
    q = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True) if k.lower() in _KEEP or k.lower() not in _DROP]
    # coreweave-style "?4650163006&board=coreweave" -> keep the bare id, drop board
    q = [(k, v) for k, v in q if not (k.lower() in ("board",) )]
    qs = "&".join(k if v == "" else f"{k}={quote(v, safe='')}" for k, v in q)
    return urlunsplit((s.scheme.lower() or "https", host, path, qs, ""))
if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]: print(canon(a))
