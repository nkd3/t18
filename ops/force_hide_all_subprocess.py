# C:\T18\ops\force_hide_all_subprocess.py
from pathlib import Path
import re, time

watcher = Path(r"C:\T18\ops\notion_git_watcher.pyw")
if not watcher.exists():
    watcher = Path(r"C:\T18\ops\notion_git_watcher.py")
if not watcher.exists():
    raise SystemExit("Watcher file not found in C:\\T18\\ops")

txt = watcher.read_text(encoding="utf-8")
bak = watcher.with_suffix(watcher.suffix + ".bak_forcehide_" + time.strftime("%Y%m%d%H%M%S"))
bak.write_text(txt, encoding="utf-8")

# Insert the hard shim right after the import block so it runs early.
shim = r"""
# --- FORCE-HIDE-SUBPROCESS (do not remove) ---
import os, sys, shlex, subprocess

# Import _GIT path if available
try:
    from ops._silent_git import _GIT
except Exception:
    _GIT = r"C:\Program Files\Git\bin\git.exe" if os.path.exists(r"C:\Program Files\Git\bin\git.exe") \
           else r"C:\Program Files (x86)\Git\bin\git.exe"

_CREATE_NO_WINDOW    = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_DETACHED_PROCESS    = 0x00000008
_STARTF_USESHOWWINDOW= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)

_ORIG_POPEN = subprocess.Popen
def _force_hidden_popen(args, *pargs, **pkwargs):
    # Normalize args to a list; kill shell
    pkwargs["shell"] = False
    if isinstance(args, str):
        args = shlex.split(args)

    # Map git token to absolute exe
    if isinstance(args, (list, tuple)) and args:
        head = str(args[0]).lower()
        if head in ("git", "git.exe", "git.cmd"):
            args = [_GIT] + list(args[1:])

    # StartupInfo + flags to suppress all windows
    si = pkwargs.get("startupinfo") or subprocess.STARTUPINFO()
    si.dwFlags |= _STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    pkwargs["startupinfo"] = si

    flags = pkwargs.get("creationflags", 0)
    flags |= (_CREATE_NO_WINDOW | _DETACHED_PROCESS)
    pkwargs["creationflags"] = flags

    # Environment: never prompt, never page
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GCM_INTERACTIVE", "Never")
    env.setdefault("GIT_ASKPASS", "echo")
    env.setdefault("SSH_ASKPASS", "echo")
    env.setdefault("GIT_PAGER", "cat")
    pkwargs["env"] = env

    return _ORIG_POPEN(args, *pargs, **pkwargs)

subprocess.Popen = _force_hidden_popen

# Let run/check_* go through our Popen override
_ORIG_RUN = subprocess.run
def _run(*a, **kw):  # keep API; Popen override applies flags
    kw["shell"] = False
    return _ORIG_RUN(*a, **kw)
subprocess.run = _run

# Also replace os.system -> go through hidden Popen
import types
def _os_system(cmd):
    args = cmd if isinstance(cmd, (list, tuple)) else shlex.split(str(cmd))
    return subprocess.Popen(args).wait()
os.system = _os_system
# --- /FORCE-HIDE-SUBPROCESS ---
"""

# 1) ensure helper import exists (so _GIT resolves cleanly if file is present)
if "from ops._silent_git import _GIT" not in txt:
    # keep it inside shim via try-except (already handled above)

    pass  # shim already handles fallback without modifying import list

# 2) Insert shim after the first import block
m = re.search(r"(^(\s*)(import|from)\b[^\n]*\n(?:[ \t]*(?:import|from)\b[^\n]*\n)*)", txt, flags=re.M)
if m:
    txt = txt[:m.end()] + shim + txt[m.end():]
else:
    txt = shim + txt

# 3) Replace any 'from subprocess import ...' -> 'import subprocess' (so our monkeypatch is used)
txt = re.sub(r"^\s*from\s+subprocess\s+import\s+.*$", "import subprocess", txt, flags=re.M)

# 4) Replace ["git", ...] with [_GIT, ...] so list-invocations don’t use shims that can flash
txt = re.sub(r"(\[)\s*[\"']git[\"']\s*,", r"\1 _GIT,", txt)

watcher.write_text(txt, encoding="utf-8")
print("Patched:", watcher)
