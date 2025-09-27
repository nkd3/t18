# Injects a "no-console" shim into your watcher so git/curl/etc. won't flash windows.
# Usage:
#   C:\T18\.venv\Scripts\python.exe C:\T18\ops\patch_hide_git_windows.py

from pathlib import Path
import sys
import re

ROOT = Path(r"C:\T18")
OPS  = ROOT / "ops"

def find_watcher():
    # Prefer what you're actually running
    primary = OPS / "notion_git_watcher.pyw"
    if primary.exists():
        return primary
    # Fallback: any *.py[w] that references build_props/Notion stuff
    cands = list(OPS.glob("*.py*")) + list(ROOT.glob("*.py*"))
    scored = []
    for f in cands:
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        score = 0
        for needle in ("build_props(", "notion", "requests", "watcher", "git "):
            if needle in t:
                score += 1
        if score >= 2:
            scored.append((score, f))
    if scored:
        scored.sort(reverse=True)
        return scored[0][1]
    return None

SHIM = r"""
# ---- BEGIN: silent-subprocess shim (prevents flashing console windows) ----
try:
    import os, subprocess
    CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)

    def _apply_silent_defaults(kwargs: dict):
        # Hide window
        si = kwargs.get("startupinfo")
        if si is None:
            si = subprocess.STARTUPINFO()
        try:
            si.dwFlags |= STARTF_USESHOWWINDOW
            si.wShowWindow = 0
        except Exception:
            pass
        kwargs["startupinfo"] = si

        # No console window
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW

        # Don’t use a shell (reduces extra conhost.exe)
        kwargs.setdefault("shell", False)

        # Make git fully non-interactive
        env = os.environ.copy()
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        env.setdefault("GCM_INTERACTIVE", "Never")
        env.setdefault("GIT_ASKPASS", "echo")
        kwargs["env"] = {**env, **kwargs.get("env", {})}
        return kwargs

    _orig_run = subprocess.run
    def _silent_run(*a, **kw):
        kw = _apply_silent_defaults(kw)
        return _orig_run(*a, **kw)
    subprocess.run = _silent_run

    _orig_popen = subprocess.Popen
    def _silent_popen(*a, **kw):
        kw = _apply_silent_defaults(kw)
        return _orig_popen(*a, **kw)
    subprocess.Popen = _silent_popen
except Exception:
    pass
# ----  END: silent-subprocess shim  ----
"""

def already_patched(text: str) -> bool:
    return "silent-subprocess shim" in text

def insert_shim(text: str) -> str:
    # Insert right after the first shebang/encoding/initial imports if present; else at top.
    lines = text.splitlines(True)
    insert_at = 0
    # skip shebang / coding lines
    while insert_at < len(lines) and (
        lines[insert_at].startswith("#!") or
        "coding" in lines[insert_at].lower()
    ):
        insert_at += 1
    # skip blank/comment banner
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1
    # if first nonblank is imports, place shim after the initial import block
    m = re.match(r"\s*import\s|\s*from\s", lines[insert_at] if insert_at < len(lines) else "")
    if m:
        j = insert_at
        while j < len(lines) and re.match(r"\s*(import|from)\s", lines[j]):
            j += 1
        insert_at = j
    lines.insert(insert_at, SHIM + "\n")
    return "".join(lines)

def main():
    watcher = find_watcher()
    if not watcher:
        print("Watcher file not found.", file=sys.stderr)
        sys.exit(1)
    txt = watcher.read_text(encoding="utf-8")
    if already_patched(txt):
        print(f"Already patched: {watcher}")
        return
    patched = insert_shim(txt)
    watcher.write_text(patched, encoding="utf-8")
    print(f"Patched (hidden subprocess): {watcher}")

if __name__ == "__main__":
    main()
