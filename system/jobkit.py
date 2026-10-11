#!/usr/bin/env python3
"""jobkit launcher - the one command that works the same on macOS, Linux and Windows.

  macOS / Linux:   python3 system/jobkit.py <tool> [arguments]
  Windows:         py -3 system\\jobkit.py <tool> [arguments]        (or: python system\\jobkit.py ...)

  <tool>   setup | daily | audit_claims | decide | state | discover_boards | intake | ... - any script under
           system/engine/tools (with or without .py)
  python   print the path of the jobkit Python (system/.venv) and exit

It runs the tool with THE JOBKIT PYTHON: system/.venv/bin/python (macOS / Linux) or system\\.venv\\Scripts\\python.exe
(Windows), the environment setup.py creates. If that environment does not exist yet it runs setup.py first, with the
Python that started this launcher (3.11 or newer). "setup" always runs with the starting Python, because that is the
one that creates the environment. Nothing else is special: arguments are passed through, the exit code is the tool's.
Paths with spaces are fine. The workspace is My Job Search/ (or $JOBKIT_WORKSPACE), as for every tool."""
import os, sys, subprocess

SYSTEM = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(SYSTEM, "engine", "tools")
VENV = os.path.join(SYSTEM, ".venv")
VPY = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")
os.environ.setdefault("PYTHONUTF8", "1")


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__); return 0
    tool, args = argv[0], argv[1:]
    if tool == "python":
        print(VPY if os.path.exists(VPY) else f"{VPY} (not created yet: run `{os.path.basename(sys.executable)} {os.path.relpath(__file__)} setup`)")
        return 0 if os.path.exists(VPY) else 1
    if sys.version_info < (3, 11):
        print(f"This Python is {sys.version_info.major}.{sys.version_info.minor}; jobkit needs 3.11 or newer (https://www.python.org/downloads/ - "
              "on Windows tick 'Add python.exe to PATH').")
        return 1
    name = tool if tool.endswith(".py") else tool + ".py"
    path = os.path.join(TOOLS, name)
    if not os.path.exists(path):
        print(f"no such tool: {name} (looked in {TOOLS})"); return 2
    if name == "setup.py":
        return subprocess.call([sys.executable, path] + args)
    if not os.path.exists(VPY):
        print("The jobkit Python environment does not exist yet; running setup first (one to five minutes)...", flush=True)
        code = subprocess.call([sys.executable, os.path.join(TOOLS, "setup.py"), "--quick"])
        if code != 0 or not os.path.exists(VPY):
            print("setup did not finish; fix the [MISSING] line it printed, then try again."); return code or 1
    return subprocess.call([VPY, path] + args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
