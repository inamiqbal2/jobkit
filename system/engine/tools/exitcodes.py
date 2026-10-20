"""EXITCODES - the four exit statuses every jobkit tool uses (v1.0, code audit M29).

The agent reading a tool's output needs to know only which of these happened; the sentence printed says why.

    OK       0   did what was asked
    FAILED   1   ran, and the check it exists to make did not pass (audit FAIL, setup blocked, manifest changed)
    REFUSED  2   would not act: bad arguments, a guard said no (SKIP guard, BUILT gate, never-places), a settings error
    OFFLINE  3   could not reach the job boards (connectivity probe failed / every board failed to answer)

Nothing else is used on purpose; a Python traceback (exit 1 from the interpreter) is always a bug to report.
"""
OK, FAILED, REFUSED, OFFLINE = 0, 1, 2, 3

NAMES = {OK: "ok", FAILED: "failed", REFUSED: "refused", OFFLINE: "offline"}
