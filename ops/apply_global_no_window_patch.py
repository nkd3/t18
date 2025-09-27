from pathlib import Path
import re, time

# Locate watcher
w = Path(r"C:\T18\ops\notion_git_watcher.pyw")
if not w.exists():
    w = Path(r"C:\T18\ops\notion_git_watcher.py")
if not w.exists():
    raise SystemExit("Watcher file not found in C:\\T18\\ops")

txt = w.read_text(encoding="utf-8")
bak = w.with_suffix(w.suffix + ".bak_popen_" + time.strftime("%Y%m%d%H%M%S"))
bak.write_text(txt, encoding="utf-8")

patch = r"""
# --- GLOBAL GIT NO-WINDOW MONKEYPATCH (auto-inserted) ---
import os, shlex, subprocess

_CREATE_NO_WINDOW   = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_DETACHED_PROCESS   = 0x00000008
_STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
_SW_HIDE            = 0

# Prefer real git.exe if available (prevents git.cmd opening a window)
_GIT_EXE = r"C:\\Program Files\\Git\\bin\\git.exe"
if not os.path.exists(_GIT_EXE):
    _GIT_EXE = r"C:\\Program Files (x86)\\Git\\bin\\git.exe"

def _looks_like_git(cmd):
    if isinstance(cmd, (list, tuple)) and cmd:
        exe = cmd[0]
    elif isinstance(cmd, str) and cmd.strip():
        # When called with a string, best-effort split
        try:
            exe = shlex.split(cmd)[0]
        except Exception:
            exe = cmd.split()[0]
    else:
        return False
    base = os.path.basename(exe).lower()
    return base in ("git", "git.exe", "git.cmd")

def _force_git_exe(cmd):
    # Replace the first token with _GIT_EXE when the command is git.*
    if isinstance(cmd, (list, tuple)) and cmd:
        if _looks_like_git(cmd):
            new = list(cmd)
            new[0] = _GIT_EXE if os.path.exists(_GIT_EXE) else new[0]
            return new
        return cmd
    elif isinstance(cmd, str):
        # Keep string form, but swap the leading token if it's git.*
        try:
            parts = shlex.split(cmd)
        except Exception:
            parts = cmd.split()
        if parts and _looks_like_git(parts):
            parts[0] = _GIT_EXE if os.path.exists(_GIT_EXE) else parts[0]
            # Recombine safely
            return " ".join(shlex.quote(p) for p in parts)
        return cmd
    return cmd

# Keep original Popen
__T18_ORIG_POPEN = subprocess.Popen

def __T18_silent_popen(*args, **kwargs):
    # Normalize the 'args' argument regardless of how it's passed
    cmd = kwargs.get("args")
    if cmd is None and args:
        cmd = args[0]

    if _looks_like_git(cmd):
        # Ensure no console window and no prompts
        si = kwargs.get("startupinfo")
        if si is None:
            si = subprocess.STARTUPINFO()
        si.dwFlags |= _STARTF_USESHOWWINDOW
        si.wShowWindow = _SW_HIDE
        kwargs["startupinfo"] = si

        flags = kwargs.get("creationflags", 0)
        flags |= (_CREATE_NO_WINDOW | _DETACHED_PROCESS)
        kwargs["creationflags"] = flags

        env = kwargs.get("env", os.environ.copy())
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        env.setdefault("GCM_INTERACTIVE", "Never")
        env.setdefault("GIT_ASKPASS", "echo")
        env.setdefault("SSH_ASKPASS", "echo")
        env.setdefault("GIT_PAGER", "cat")
        kwargs["env"] = env

        # Avoid shell to prevent flashing via the shell
        kwargs["shell"] = False

        # Force git.exe instead of git/cmd shims
        if "args" in kwargs:
            kwargs["args"] = _force_git_exe(kwargs["args"])
        else:
            args = (_force_git_exe(args[0]),) + args[1:]

    return __T18_ORIG_POPEN(*args, **kwargs)

# Monkeypatch
subprocess.Popen = __T18_silent_popen
# --- END GLOBAL GIT NO-WINDOW MONKEYPATCH ---
"""

# Insert patch right after the initial imports (once)
if "# --- GLOBAL GIT NO-WINDOW MONKEYPATCH" not in txt:
    m = re.search(r"(^(\s*)(import|from)\b[^\n]*\n(?:[ \t]*(?:import|from)\b[^\n]*\n)*)", txt, flags=re.M)
    if m:
        start = m.end()
        txt = txt[:start] + patch + txt[start:]
    else:
        txt = patch + txt

w.write_text(txt, encoding="utf-8")
print("Injected global Popen monkeypatch into", w)
