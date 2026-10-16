#!/usr/bin/env python3
"""MANIFEST - the source lock of the jobkit engine (v0.5).

system/engine/MANIFEST.sha256 lists the SHA-256 of every file under system/engine/ (except itself, caches and OS
litter). The release script writes it; setup.py checks it on every run and reports
  "Engine: original (v0.5)"                       every file matches the shipped manifest
  "Engine: MODIFIED - N files (see 'show my modifications')"   something under system/engine differs
The same module locks and unlocks the engine on disk (read-only files and folders; Windows: attrib +R), so an
accidental edit fails loudly and a deliberate one goes through the "modify:" command in CLAUDE.md.

  <jobkit python> manifest.py generate     # (release script / after an approved modification) rewrite MANIFEST.sha256
  <jobkit python> manifest.py check        # exit 0 = original, 1 = modified / no manifest; prints the differing files
  <jobkit python> manifest.py status       # the one-line status setup.py prints
  <jobkit python> manifest.py lock         # chmod a-w (attrib +R) everything under system/engine
  <jobkit python> manifest.py unlock       # chmod u+w (attrib -R) everything under system/engine
Nothing here ever touches the person's area (My Job Search/)."""
import sys as _sys0
try: _sys0.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows: never die on a non-cp1252 character
except Exception: pass
import os, sys, hashlib, datetime, stat, subprocess

JOBKIT_VERSION = "v0.6"
HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
MANIFEST = os.path.join(ENGINE, "MANIFEST.sha256")
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_FILES = {"MANIFEST.sha256", ".DS_Store", "Thumbs.db"}
WIN = os.name == "nt"


def _files():
    out = []
    for root, dirs, files in os.walk(ENGINE):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP_FILES or f.endswith(".pyc"):
                continue
            out.append(os.path.relpath(os.path.join(root, f), ENGINE).replace(os.sep, "/"))
    return out


def _sha(path):
    """SHA-256 of the file with CRLF line endings normalized to LF for text files (a file without NUL bytes), so a
    checkout under Git for Windows' core.autocrlf=true (or an editor that saved CRLF) still matches the shipped
    manifest. Binary files (NUL byte in the first 8 KB) hash byte-for-byte."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        data = fh.read()
    if b"\x00" not in data[:8192]:
        data = data.replace(b"\r\n", b"\n")
    h.update(data)
    return h.hexdigest()


def generate():
    lines = [f"# jobkit engine manifest {JOBKIT_VERSION} generated {datetime.date.today().isoformat()} - every file under system/engine/"]
    for rel in _files():
        lines.append(f"{_sha(os.path.join(ENGINE, rel))}  {rel}")
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return len(lines) - 1


def read():
    """-> (version, {relpath: sha}) or (None, None) when there is no manifest."""
    if not os.path.exists(MANIFEST):
        return None, None
    version, entries = "?", {}
    for line in open(MANIFEST, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("#"):
            import re
            m = re.search(r"manifest (v[\d.]+)", line)
            if m:
                version = m.group(1)
            continue
        if "  " in line:
            sha, rel = line.split("  ", 1)
            entries[rel.strip()] = sha.strip()
    return version, entries


def check():
    """-> dict(version, changed[], missing[], added[], ok: bool, has_manifest: bool)."""
    version, entries = read()
    if entries is None:
        return dict(version=None, changed=[], missing=[], added=[], ok=False, has_manifest=False)
    now = {rel: _sha(os.path.join(ENGINE, rel)) for rel in _files()}
    changed = sorted(r for r in entries if r in now and now[r] != entries[r])
    missing = sorted(r for r in entries if r not in now)
    added = sorted(r for r in now if r not in entries)
    return dict(version=version, changed=changed, missing=missing, added=added,
                ok=not (changed or missing or added), has_manifest=True)


def status_line():
    c = check()
    if not c["has_manifest"]:
        return f"Engine: no manifest (development checkout; the release script writes system/engine/MANIFEST.sha256)"
    if c["ok"]:
        return f"Engine: original ({c['version']})"
    n = len(c["changed"]) + len(c["missing"]) + len(c["added"])
    return f"Engine: MODIFIED - {n} file{'s' if n != 1 else ''} (see 'show my modifications')"


def _walk_all():
    for root, dirs, files in os.walk(ENGINE):
        for f in files:
            yield os.path.join(root, f), False
        for d in dirs:
            yield os.path.join(root, d), True
    yield ENGINE, True


def lock():
    """Read-only on disk for every file and folder under system/engine (folders too, so nothing can be added).
    Python still imports and runs everything; it simply stops writing .pyc caches there."""
    n = 0
    for p, is_dir in _walk_all():
        try:
            if WIN:
                if not is_dir:
                    subprocess.run(["attrib", "+R", p], capture_output=True)
            else:
                mode = os.stat(p).st_mode
                os.chmod(p, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            n += 1
        except OSError:
            pass
    return n


def unlock():
    n = 0
    for p, is_dir in _walk_all():
        try:
            if WIN:
                if not is_dir:
                    subprocess.run(["attrib", "-R", p], capture_output=True)
            else:
                mode = os.stat(p).st_mode
                os.chmod(p, mode | stat.S_IWUSR)
            n += 1
        except OSError:
            pass
    return n


def is_locked():
    """True when the engine folder itself refuses writes (the state setup.py leaves it in)."""
    if WIN:
        probe = os.path.join(HERE, "setup.py")
        try:
            return not os.access(probe, os.W_OK)
        except OSError:
            return False
    return not os.access(ENGINE, os.W_OK)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "generate":
        if is_locked():
            print("system/engine is locked; run `manifest.py unlock` first"); sys.exit(1)
        print(f"MANIFEST.sha256 written: {generate()} files")
    elif cmd == "check":
        c = check()
        print(status_line())
        for k in ("changed", "missing", "added"):
            for r in c[k]:
                print(f"  {k}: {r}")
        sys.exit(0 if c["ok"] else 1)
    elif cmd == "status":
        print(status_line())
    elif cmd == "lock":
        print(f"locked: {lock()} entries under {ENGINE}")
    elif cmd == "unlock":
        print(f"unlocked: {unlock()} entries under {ENGINE}")
    else:
        print(__doc__)
